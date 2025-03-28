#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import List, Dict, Any, Optional, Tuple, Mapping
from dataclasses import dataclass, field
from dotenv import load_dotenv
import base64
from datetime import datetime
import aiohttp

# load .env file
load_dotenv()

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("src"))

# Import standard OpenAI Agents SDK
from agents import Agent, Runner, RunContextWrapper, RunHooks, Usage, Tool, function_tool

# Import Carrier extensions
from src.carrier.extensions.carrier_agent import AgentMemory, CarrierAgent
from src.carrier.clients.discord_client import DiscordAgentClient
from src.carrier.clients.instagram_client import InstagramAgentClient
from src.carrier.utils.logging import configure_logging

# Configure logging
logger = configure_logging()

# Define the weather tool function
@function_tool
async def GET_WEATHER(location: str) -> str:
    """
    Get the current weather for a location.
    
    Args:
        location: The location to get weather for (not actually used in this implementation)
        
    Returns:
        A string describing the weather
    """
    # This is a simple implementation that always returns "sunny"
    # Handle default case inside the function instead of in the parameter
    if not location or location.lower() == "default":
        location = "default location"
        
    logger.info(f"Weather tool called for location: {location}")
    return "sunny"

async def load_character_file(file_path: str) -> Dict[str, Any]:
    """Load and parse the character file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Character file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_available_tools(tool_config: List[str]) -> Tuple[List[Any], Dict[str, str]]:
    """
    Get available tools and their descriptions based on configuration.
    
    Args:
        tool_config: List of tool names from character configuration
        
    Returns:
        Tuple containing (configured_tools, tool_descriptions)
    """
    configured_tools = []
    tool_descriptions = {}
    
    # Map tool names to actual tool functions
    tool_mapping = {
        "GET_WEATHER": GET_WEATHER,
        # Add other tools here as they are implemented
    }
    
    for tool_name in tool_config:
        if tool_name in tool_mapping:
            tool = tool_mapping[tool_name]
            configured_tools.append(tool)
            
            # Get tool description and usage examples
            doc = tool.__doc__ or "No description available"
            description = " ".join(line.strip() for line in doc.split('\n')).strip()
            
            # Add specific usage examples based on the tool
            if tool_name == "GET_WEATHER":
                usage = "\nExample usage: get_weather('New York') would return information about the weather in New York."
                description += usage
                
            tool_descriptions[tool_name] = description
        else:
            tool_descriptions[tool_name] = "(Tool configured but not implemented)"
            
    return configured_tools, tool_descriptions

def build_system_prompt(character_data: Dict[str, Any], client: str = "generic", tool_descriptions: Dict[str, str] = None) -> str:
    """Build a comprehensive system prompt from character data"""
    
    # Start with the basic system prompt
    system_prompt = character_data.get("system", "")
    
    # Add bio information
    bio = character_data.get("bio", [])
    if bio:
        system_prompt += "\n\n## About You\n" + "\n".join([f"- {item}" for item in bio])
    
    # Add background/lore
    lore = character_data.get("lore", [])
    if lore:
        system_prompt += "\n\n## Your Background\n" + "\n".join([f"- {item}" for item in lore])
    
    # Add communication style
    style = character_data.get("style", {})
    all_style = style.get("all", [])
    chat_style = style.get("chat", [])
    
    if all_style or chat_style:
        system_prompt += "\n\n## Your Communication Style\n"
        if all_style:
            system_prompt += "\n".join([f"- {item}" for item in all_style])
        if chat_style:
            system_prompt += "\n" + "\n".join([f"- {item}" for item in chat_style])
    
    # Add conversation examples if available
    examples = character_data.get("messageExamples", [])
    if examples and len(examples) > 0:
        system_prompt += "\n\n## Example Conversations\n"
        for i, example in enumerate(examples[:3]):  # Limit to 3 examples
            system_prompt += f"\nExample {i+1}:\n"
            for message in example:
                role = "User" if message.get("user") != character_data.get("name") else character_data.get("name")
                content = message.get("content", {}).get("text", "")
                system_prompt += f"{role}: {content}\n"
    
    # Add client-specific context
    system_prompt += "\n\n## Client Context\n"
    if client == "discord":
        system_prompt += "- You are interacting in a Discord server.\n"
        system_prompt += "- You'll only respond when someone mentions you by name or tags you.\n"
        system_prompt += "- Keep responses appropriately sized for a chat client.\n"
        system_prompt += "- Remember that many people might be watching this conversation.\n"
    elif client == "instagram":
        system_prompt += "- You are interacting on Instagram via direct messages.\n"
        system_prompt += "- These are usually private one-on-one conversations.\n"
        system_prompt += "- Keep responses concise and engaging for the client.\n"
        system_prompt += "- Users might share images or stories with you, but you can only respond with text.\n"
    
    # Enhanced section for available tools
    system_prompt += "\n\n## Available Tools\n"
    
    if not tool_descriptions or len(tool_descriptions) == 0:
        system_prompt += "- You don't have any tools available to use.\n"
    else:
        system_prompt += "You have access to the following tools:\n"
        
        for tool_name, description in tool_descriptions.items():
            system_prompt += f"- {tool_name.upper()}: {description}\n"
    
    return system_prompt

async def initialize_agent(character_file: str, client: str = "generic") -> Tuple[Agent, AgentMemory]:
    """Initialize a Carrier agent from character file"""
    logger.info(f"Initializing agent from {character_file} for {client}")
    
    # Load the character file
    character_data = await load_character_file(character_file)
    
    # Get tools configuration from character data
    tool_config = character_data.get("tools", [])
    
    # Get configured tools and their descriptions
    configured_tools, tool_descriptions = get_available_tools(tool_config)
    
    # Build the system prompt from character data (including tool descriptions)
    system_prompt = build_system_prompt(character_data, client, tool_descriptions)
    
    # Initialize the standard OpenAI Agent
    base_agent = Agent(
        name=character_data.get("name", "Agent"),
        instructions=system_prompt,
        model=character_data.get("model", "gpt-4o-mini"),
        tools=configured_tools 
    )
    
    # Initialize memory
    memory = AgentMemory(client=client)
    
    # Convert to CarrierAgent with memory
    agent = CarrierAgent.from_agent(base_agent, memory)
    
    # List tools in uppercase with brackets between each tool
    tools_list = ", ".join([tool.name.upper() for tool in agent.tools]) if agent.tools else "NO TOOLS"
    logger.info(f"{agent.name} initialized with {tools_list} for {client}")
    
    return agent, memory

async def generate_image(description: str) -> Optional[bytes]:
    """
    Generate an image using the local image generation API
    
    Args:
        description: A detailed description of the image to generate
        
    Returns:
        Bytes of the generated image, or None if generation failed
    """
    try:
        # Use aiohttp to make an async HTTP request
        async with aiohttp.ClientSession() as session:
            payload = {"image_description": description}
            headers = {"Content-Type": "application/json"}
            
            # Make the request to the local image generation API
            async with session.post(
                "https://localhost:9080", 
                json=payload,
                headers=headers,
                ssl=False  # Disable SSL verification for local development
            ) as response:
                if response.status != 200:
                    logger.error(f"Image generation API returned status {response.status}")
                    return None
                
                # Parse the response JSON to get the base64 image data
                response_data = await response.json()
                if not response_data or "base64_image" not in response_data:
                    logger.error("No base64 image data in response")
                    return None
                
                # Decode the base64 string to bytes
                image_bytes = base64.b64decode(response_data["base64_image"])
                return image_bytes
    
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

async def main():
    """Main function to run agent clients based on character configuration"""
    # Load environment variables
    load_dotenv()
    
    # Character files to load
    character_files = [
        "characters/assistantbot.json",
        # "characters/questionbot.json",
        # "characters/answerbot.json",
        # "characters/plannerbot.json",
    ]
    
    # Tasks to gather for concurrent execution
    client_tasks = []
    
    # Create and configure clients for each agent
    for char_file in character_files:
        try:
            # Load character data
            character_data = await load_character_file(char_file)
            username = character_data.get("username")
            supported_clients = character_data.get("clients", [])
            
            # Initialize Discord client if supported
            if "Discord" in supported_clients:
                discord_token = os.getenv(f"{username}_DISCORD_API_TOKEN")
                if discord_token:
                    # Initialize agent for Discord
                    agent, memory = await initialize_agent(char_file, client="discord")
                    
                    # Create dedicated Discord client for this agent
                    discord_client = DiscordAgentClient(agent, memory)
                    
                    # Configure Discord client based on character configuration
                    discord_config = character_data.get("discord_config", {})
                    
                    # Set initial channel if specified in character file
                    if "initial_channel" in discord_config:
                        discord_client.initial_channel = discord_config["initial_channel"]
                    
                    # Set initial message if specified in character file
                    if "initial_message" in discord_config:
                        discord_client.initial_message = discord_config["initial_message"]
                    
                    client_tasks.append(asyncio.create_task(
                        discord_client.start(discord_token)
                    ))
                else:
                    logger.error(f"Missing Discord token for {username}")
            
            # Initialize Instagram client if supported
            if "Instagram" in supported_clients:
                instagram_token = os.getenv(f"{username}_INSTAGRAM_ACCESS_TOKEN")
                if instagram_token:
                    # Initialize agent for Instagram
                    agent, memory = await initialize_agent(char_file, client="instagram")
                    
                    # Create dedicated Instagram client for this agent
                    instagram_client = InstagramAgentClient(agent, memory)
                    client_tasks.append(asyncio.create_task(
                        instagram_client.run(instagram_token)
                    ))
                else:
                    logger.error(f"Missing Instagram token for {username}")
                    
            # Support for other client types can be added here
                
        except Exception as e:
            logger.error(f"Error initializing agent from {char_file}: {e}")
    
    # Run all clients concurrently
    if client_tasks:
        await asyncio.gather(*client_tasks)
    else:
        logger.error("No clients were successfully initialized")
    


if __name__ == "__main__":
    # Run the asyncio event loop
    asyncio.run(main())
