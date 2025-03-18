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

# Import Carrier agent framework
from agents import Agent, Runner, RunContextWrapper, RunHooks, Usage, TResponseInputItem
from agents.tool import function_tool  # Import the function_tool helper
from agents.agent import AgentMemory  # Import AgentMemory from its new location

# Import clients from their new modules
from src.clients.discord_client import DiscordAgentClient, DiscordHooks
from src.clients.instagram_client import InstagramAgentClient, InstagramHooks

# Import logging utility
from utils.logging import configure_logging

# Configure logging
logger = configure_logging()

# Character file path
character_file = "characters/assistantbot.json"

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


def build_system_prompt(character_data: Dict[str, Any], client: str = "generic") -> str:
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
    
    # Add information about available tools
    system_prompt += "\n\n## Available Tools\n"
    system_prompt += "- You have access to a weather tool that can tell you the current weather.\n"
    system_prompt += "- You can use this tool by calling get_weather() with an optional location parameter.\n"
    system_prompt += "- The weather is always 'sunny' in this implementation.\n"
    system_prompt += "- Example usage: When a user asks about the weather, you can call the get_weather tool and include the result in your response.\n"
    
    return system_prompt


async def initialize_agent(character_file: str, client: str = "generic") -> Tuple[Agent, AgentMemory]:
    """Step 1: Agent Initialization"""
    logger.info(f"Initializing agent from {character_file} for {client}")
    
    # Load the character file
    character_data = await load_character_file(character_file)
    
    # Build the system prompt from character data
    system_prompt = build_system_prompt(character_data, client)
    
    # Initialize the agent
    agent = Agent(
        name=character_data.get("name", "Agent"),
        instructions=system_prompt,
        model=character_data.get("model", "gpt-4o-mini"),
        tools=[GET_WEATHER]  # Use the decorated function directly
    )
    
    # Initialize memory
    memory = AgentMemory(client=client)
    
    #  list tools in uppercase with brackets between each tool
    tools_list = ", ".join([tool.name.upper() for tool in agent.tools])
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
        "characters/plannerbot.json",
        # Add more character files as needed
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
            
            # Initialize the agent
            agent, memory = await initialize_agent(char_file)
            
            # Initialize clients based on character configuration
            if "Discord" in supported_clients:
                discord_token = os.getenv(f"{username}_DISCORD_API_TOKEN")
                if discord_token:
                    # Create dedicated Discord client for this agent
                    discord_client = DiscordAgentClient(agent, memory)
                    client_tasks.append(asyncio.create_task(
                        discord_client.start(discord_token)
                    ))
                else:
                    logger.error(f"Missing Discord token for {username}")
            
            if "Instagram" in supported_clients:
                instagram_token = os.getenv(f"{username}_INSTAGRAM_ACCESS_TOKEN")
                if instagram_token:
                    # Create dedicated Instagram client for this agent
                    instagram_client = InstagramAgentClient(agent, memory)
                    client_tasks.append(asyncio.create_task(
                        instagram_client.run(instagram_token)
                    ))
                else:
                    logger.error(f"Missing Instagram token for {username}")
                    
            if "Twitter" in supported_clients:
                # Similar logic for Twitter client
                pass
                
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