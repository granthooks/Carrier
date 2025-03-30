"""
Discord Client for Carrier Agent Framework

This module contains the DiscordAgentClient and related hooks for
interacting with Discord using the discord.py library.
"""

import os
import logging
import re
from typing import Dict, Tuple, List, Any
import discord
from discord.ext import commands
from datetime import datetime

from agents import Agent, Runner, RunContextWrapper, RunHooks

from ..utils.logging import configure_logging
from ..utils.hooks_util import add_memory_hooks
from ..extensions.carrier_agent import AgentMemory

# Configure logging
logger = configure_logging()

class DiscordHooks(RunHooks):
    """Discord-specific hooks for the agent runtime"""

    def __init__(self):
        self.processed_messages = 0
        self.client = "discord"

    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Called when agent processing begins"""
        self.processed_messages += 1

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Any) -> None:
        """Called when a tool execution begins"""
        logger.info(f"[{self.client}] Executing tool: {tool.name}")

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Any, result: str) -> None:
        """Called when a tool execution completes"""
        logger.info(f"[{self.client}] Tool {tool.name} completed.")

    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when agent processing completes"""
        memory = self._get_memory_from_context(context)
        
        # Store conversation in memory for future context
        if memory and hasattr(output, 'content') and output.content:
            memory.conversation_history.append({
                "role": "assistant",
                "content": output.content,
                "timestamp": "now",  # In a real implementation, use actual timestamp
                "client": self.client
            })
            logger.info(f"[{self.client}] Memory contains {len(memory.conversation_history)} messages")
        
        logger.info(f"[{self.client}] Response generated and stored in memory")
    
    def _get_memory_from_context(self, context: RunContextWrapper) -> AgentMemory:
        """Get memory object from context if available."""
        if not context or not context.context:
            return None
            
        # If context is directly a memory object
        if isinstance(context.context, AgentMemory):
            return context.context
            
        # If context has a memory attribute
        if hasattr(context.context, 'memory'):
            return context.context.memory
            
        return None


def get_hooks_with_memory(agent: Agent, user_id: str, room_id: str) -> RunHooks:
    """Get appropriate hooks with memory context if available.
    
    Args:
        agent: Agent to use
        user_id: User ID for memory context
        room_id: Room ID for memory context
        
    Returns:
        Appropriate hooks instance with memory context if available
    """
    return add_memory_hooks(
        base_hooks_class=DiscordHooks,
        agent=agent,
        user_id=user_id,
        room_id=room_id,
        conversation_limit=10,
        client_name="Discord"
    )


class DiscordAgentClient(discord.Client):
    """Discord client that manages a single agent interaction"""
    
    def __init__(self, agent: Agent, memory: AgentMemory, **kwargs):
        """Initialize the Discord client for a specific agent"""
        # Configure discord.py client settings
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        
        # Initialize the discord.py client
        super().__init__(intents=intents, **kwargs)
        
        # Store agent and memory
        self.agent = agent
        self.memory = memory
        
        # Client configuration
        self.initial_channel = None  # Can be set to send initial message on startup
        self.initial_message = None  # Message to send on startup
        self.prefix = "!"  # Command prefix
        
        # Client state
        self.ready = False
    
    async def on_ready(self):
        """Called when the bot is ready and connected to Discord"""
        self.ready = True
        logger.info(f"Discord client for {self.agent.name} is connected as {self.user.name} ({self.user.id})")
        
        # If configured with initial channel, send initial message
        if self.initial_channel and self.initial_message:
            try:
                channel = await self.fetch_channel(self.initial_channel)
                if channel:
                    await channel.send(self.initial_message)
                    logger.info(f"Sent initial message to channel {channel.name}")
            except Exception as e:
                logger.error(f"Error sending initial message: {e}")
    
    async def on_message(self, message):
        """Called when a message is received"""
        # Ignore own messages
        if message.author == self.user:
            return
            
        # Check if the bot was mentioned or addressed by name
        bot_mentioned = self.user.mentioned_in(message)
        name_mentioned = self.agent.name.lower() in message.content.lower()
        
        # Only respond to mentions or direct messages
        if bot_mentioned or name_mentioned or isinstance(message.channel, discord.DMChannel):
            await self.process_agent_message(message)
    
    async def process_agent_message(self, message):
        """Process a message with the agent"""
        try:
            # Prepare message content
            content = message.content
            
            # Remove bot mention or name from content
            if f"<@{self.user.id}>" in content:
                content = content.replace(f"<@{self.user.id}>", "").strip()
            elif self.agent.name.lower() in content.lower():
                content = content.replace(self.agent.name, "", flags=re.IGNORECASE).strip()
            
            # Set typing indicator
            async with message.channel.typing():
                # Store user message in memory
                self.memory.conversation_history.append({
                    "role": "user",
                    "content": content,
                    "timestamp": str(message.created_at),
                    "client": "discord",
                    "user_id": str(message.author.id)
                })
                
                # Create hooks with memory context
                hooks = get_hooks_with_memory(
                    agent=self.agent,
                    user_id=str(message.author.id),
                    room_id=str(message.channel.id)
                )
                
                # Process message with agent
                result = await Runner.run(
                    starting_agent=self.agent,
                    input=content,
                    context=self.memory,
                    hooks=hooks
                )
                
                # Get final output
                response = result.final_output
                
                # Send response in chunks if needed (Discord has a 2000 character limit)
                if len(response) <= 2000:
                    await message.channel.send(response)
                else:
                    # Split response into chunks
                    chunks = [response[i:i+1990] for i in range(0, len(response), 1990)]
                    for i, chunk in enumerate(chunks):
                        # Add continuation indicator
                        if i < len(chunks) - 1:
                            chunk += "... (continued)"
                        if i > 0:
                            chunk = "... " + chunk
                        await message.channel.send(chunk)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await message.channel.send(f"I encountered an error: {str(e)}")
    
    async def start(self, token, *args, **kwargs):
        """Start the Discord client with the provided token"""
        logger.info(f"Starting Discord client for {self.agent.name}")
        await super().start(token, *args, **kwargs)
