#!/usr/bin/env python3
"""
Discord Client for Carrier Agent Framework

This module contains the DiscordAgentClient and related hooks for
interacting with Discord using the discord.py library.
"""

import os
import logging
from typing import Dict, Tuple, List, Any
import discord
from discord.ext import commands

from agents import Agent, Runner, RunContextWrapper, RunHooks
from ..utils.logging import configure_logging

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
        logger.info(f"[{self.client}] Tool {tool.name} completed with result: {result}")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when agent processing completes"""
        from ..agents.agent import AgentMemory  # Import here to avoid circular imports
        
        memory: AgentMemory = context.context
        
        # Store conversation in memory for future context
        if hasattr(output, 'content') and output.content:
            memory.conversation_history.append({
                "role": "assistant",
                "content": output.content,
                "timestamp": "now",  # In a real implementation, use actual timestamp
                "client": self.client
            })
            logger.info(f"[{self.client}] Memory contains {len(memory.conversation_history)} messages")
        
        logger.info(f"[{self.client}] Response generated and stored in memory")


class DiscordAgentClient(commands.Bot):
    """Discord client that manages a single agent interaction"""
    
    def __init__(self, agent: Agent, memory: Any):
        """Initialize the Discord client for a specific agent"""
        # Setup Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        
        # Initialize the bot
        super().__init__(command_prefix='!', intents=intents)
        
        # Store agent and memory directly
        self.agent = agent
        self.memory = memory
        
        # Setup event handlers
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Set up event handlers for Discord events"""
        # These event handlers are already bound due to how discord.py works
        # We're just defining them as methods of our class
        pass
    
    async def on_ready(self):
        """Called when the bot has connected to Discord"""
        logger.info(f"Discord bot connected as {self.user}")
    
    async def on_message(self, message: discord.Message):
        """Called when a message is received"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if the bot is mentioned
        if self.user.mentioned_in(message):
            # Process directly with this client's agent
            # No need for agent lookup since there's only one
            await self.process_message(message)
        
        # Process commands
        await self.process_commands(message)
    
    async def process_message(self, message: discord.Message):
        """Process a message that mentions the bot"""
        # Extract the message content without the mention
        content = message.clean_content
        
        # Remove the mention of the bot
        for mention in message.mentions:
            if mention == self.user:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        
        content = content.strip()
        
        logger.info(f"[Discord] Processing mention for {self.agent.name}: {content}")
        
        # Process with the agent
        await self.process_with_agent(message, content, self.agent, self.memory)
    
    async def process_with_agent(self, message: discord.Message, content: str, agent: Agent, memory: Any):
        """Process a message with the specified agent"""
        # Add message to memory
        memory.conversation_history.append({
            "role": "user",
            "content": content,
            "user_id": str(message.author.id),
            "username": message.author.display_name,
            "timestamp": str(message.created_at),
            "client": "discord"
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
                logger.info(f"[Discord] Agent {agent.name} response: {response}")
                
                # Update input items for future context
                return result.to_input_list()
            
            except Exception as e:
                logger.error(f"[Discord] Error processing message: {e}")
                await message.channel.send(f"I encountered an error while processing your message. Please try again later.") 