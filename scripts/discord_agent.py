#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import List, Dict, Any, Optional, Tuple, Mapping
from dataclasses import dataclass, field
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("../src"))

# Import Carrier agent framework
from agents import Agent, Runner, RunContextWrapper, RunHooks, Usage, TResponseInputItem
from agents.tool import function_tool  # Import the function_tool helper
# Import logging utility
from utils.logging import configure_logging

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


@dataclass
class AgentMemory:
    """Maintains the agent's memory between interactions"""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_info: Dict[str, Any] = field(default_factory=dict)
    last_topics: List[str] = field(default_factory=list)
    
    
async def load_character_file(file_path: str) -> Dict[str, Any]:
    """Load and parse the character file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Character file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_system_prompt(character_data: Dict[str, Any]) -> str:
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
    
    # Add specific discord context
    system_prompt += "\n\n## Platform Context\n"
    system_prompt += "- You are interacting in a Discord server.\n"
    system_prompt += "- You'll only respond when someone mentions you by name or tags you.\n"
    system_prompt += "- Keep responses appropriately sized for a chat platform.\n"
    system_prompt += "- Remember that many people might be watching this conversation.\n"
    
    # Add information about available tools
    system_prompt += "\n\n## Available Tools\n"
    system_prompt += "- You have access to a weather tool that can tell you the current weather.\n"
    system_prompt += "- You can use this tool by calling get_weather() with an optional location parameter.\n"
    system_prompt += "- The weather is always 'sunny' in this implementation.\n"
    system_prompt += "- Example usage: When a user asks about the weather, you can call the get_weather tool and include the result in your response.\n"
    
    return system_prompt


async def initialize_agent(character_file: str) -> Tuple[Agent, AgentMemory]:
    """Step 1: Agent Initialization"""
    logger.info(f"Initializing agent from {character_file}")
    
    # Load the character file
    character_data = await load_character_file(character_file)
    
    # Build the system prompt from character data
    system_prompt = build_system_prompt(character_data)
    
    # Initialize the agent
    agent = Agent(
        name=character_data.get("name", "Agent"),
        instructions=system_prompt,
        model=character_data.get("model", "gpt-4o-mini"),
        tools=[GET_WEATHER]  # Use the decorated function directly
    )
    
    # Initialize memory
    memory = AgentMemory()
    
    #  list tools in uppercase with brackets between each tool
    tools_list = ", ".join([tool.name.upper() for tool in agent.tools])
    logger.info(f"{agent.name} initialized with {tools_list}")
    return agent, memory


class DiscordHooks(RunHooks):
    """Implements hooks for the runtime loop stages during Discord processing"""
    
    def __init__(self):
        self.processed_messages = 0
    
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Step 3: Message Processing pipeline begins"""
        # logger.info(f"Processing message for {agent.name}...")
        self.processed_messages += 1
    
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Any) -> None:
        """Step 5: Action Execution begins"""
        logger.info(f"Executing tool: {tool.name}")
    
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Any, result: str) -> None:
        """Step 5: Action Execution completes"""
        logger.info(f"Tool {tool.name} completed with result: {result}")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Step 6: Evaluation and Step 7: Memory Storage complete"""
        memory: AgentMemory = context.context
        
        # Store conversation in memory for future context
        if hasattr(output, 'content') and output.content:
            memory.conversation_history.append({
                "role": "assistant",
                "content": output.content,
                "timestamp": "now"  # In a real implementation, use actual timestamp
            })
            logger.info(f"Memory contains {len(memory.conversation_history)} messages")
        
        logger.info(f"Response generated and stored in memory")


class DiscordAgentClient(commands.Bot):
    """Discord client that manages agent interactions"""
    
    def __init__(self, agents_mapping: Dict[str, Tuple[Agent, AgentMemory]]):
        """Initialize the Discord client"""
        # Setup Discord intents (permissions)
        intents = discord.Intents.default()
        intents.message_content = True  # Needed to read message content
        
        # Initialize the bot with a command prefix (for potential commands)
        super().__init__(command_prefix='!', intents=intents)
        
        # Store agent mapping
        self.agents_mapping = agents_mapping
        
        # Set up our event handlers
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Set up event handlers for Discord events"""
        # These event handlers are already bound due to how discord.py works
        # We're just defining them as methods of our class
        pass
    
    async def on_ready(self):
        """Called when the bot has connected to Discord"""
        logger.info(f"Bot connected as {self.user}")
        logger.info(f"Available agents: {', '.join(self.agents_mapping.keys())}")
    
    async def on_message(self, message: discord.Message):
        """Called when a message is received"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if the bot is mentioned
        if self.user.mentioned_in(message):
            await self.process_mention(message)
        
        # Process commands (if we add any)
        await self.process_commands(message)
    
    async def process_mention(self, message: discord.Message):
        """Process a message that mentions the bot"""
        # Extract the message content without the mention
        content = message.clean_content
        
        # Remove the mention of the bot
        for mention in message.mentions:
            if mention == self.user:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        
        content = content.strip()
        
        # Determine which agent to use (default to the first one for now)
        agent_name = self.determine_addressed_agent(message.content)
        
        if agent_name in self.agents_mapping:
            agent, memory = self.agents_mapping[agent_name]
        else:
            # Default to the first agent if no match
            agent_name = list(self.agents_mapping.keys())[0]
            agent, memory = self.agents_mapping[agent_name]
        
        logger.info(f"Processing mention for {agent_name}: {content}")
        
        # Process with the agent
        await self.process_with_agent(message, content, agent, memory)
    
    def determine_addressed_agent(self, content: str) -> str:
        """Determine which agent is being addressed in the message"""
        # Simple implementation: check if agent name appears in the message
        # In a more advanced implementation, could use NLP to determine the addressed agent
        for agent_name in self.agents_mapping.keys():
            if agent_name.lower() in content.lower():
                return agent_name
        
        # Default to the first agent
        return list(self.agents_mapping.keys())[0]
    
    async def process_with_agent(self, message: discord.Message, content: str, agent: Agent, memory: AgentMemory):
        """Process a message with the specified agent"""
        # Add message to memory
        memory.conversation_history.append({
            "role": "user",
            "content": content,
            "user_id": str(message.author.id),
            "username": message.author.display_name,
            "timestamp": str(message.created_at)
        })
        
        # Create input items from conversation history
        # For simplicity, we'll just use the current message as input
        input_items = [{"content": content, "role": "user"}]
        
        # Set up hooks
        hooks = DiscordHooks()
        
        # Send typing indicator
        async with message.channel.typing():
            try:
                # Process with agent
                result = await Runner.run(
                    agent,
                    input_items,
                    context=memory,
                    hooks=hooks
                )
                
                # Get response
                response = result.final_output
                
                # Send response to Discord
                await message.channel.send(response)
                
                # Log the agent's response
                logger.info(f"Agent {agent.name} response: {response}")
                
                # Update input items for future context
                return result.to_input_list()
            
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await message.channel.send(f"I encountered an error while processing your message. Please try again later.")


async def main():
    """Main function to run the Discord bot"""
    # Load environment variables
    load_dotenv()
    
    # Get Discord credentials
    discord_token = os.getenv("DISCORD_API_TOKEN")
    if not discord_token:
        logger.error("DISCORD_API_TOKEN not found in environment variables")
        return
    
    # Initialize agents
    agents_mapping = {}
    
    # Initialize Assistant Bot agent
    try:
        assistantbot_agent, assistantbot_memory = await initialize_agent("../characters/assistantbot.json")
        agents_mapping[assistantbot_agent.name] = (assistantbot_agent, assistantbot_memory)
        
        # Could add more agents here in the future
    except Exception as e:
        logger.error(f"Error initializing agents: {e}")
        return
    
    # Create and run the Discord client
    client = DiscordAgentClient(agents_mapping)
    
    try:
        logger.info("Starting Discord bot...")
        await client.start(discord_token)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"Error running Discord bot: {e}")
    finally:
        # This will only run if the bot is stopped
        logger.info("Closing Discord connection...")
        await client.close()


if __name__ == "__main__":
    # Run the asyncio event loop
    asyncio.run(main())
