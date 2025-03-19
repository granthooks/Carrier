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
from datetime import datetime

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
        # Debug the output structure to understand what we're getting
        logger.debug(f"[{self.client}] Output type: {type(output)}")
        logger.debug(f"[{self.client}] Output attrs: {dir(output)}")
        
        # Extract the content, considering different possible structures
        response_content = None
        
        # Try different ways to access the content
        if hasattr(output, 'content') and output.content:
            response_content = output.content
        elif hasattr(output, 'text') and output.text:
            response_content = output.text
        elif hasattr(output, 'message') and hasattr(output.message, 'content') and output.message.content:
            response_content = output.message.content
        elif isinstance(output, dict) and 'content' in output:
            response_content = output['content']
        elif isinstance(output, str):
            response_content = output
            
        # If we have response content, store it
        if response_content:
            # Use the agent's memory system if available
            if hasattr(agent, 'memory_system') and agent.memory_system and hasattr(agent, 'store_message'):
                try:
                    # Create the message data
                    content = {"text": response_content}
                    room_id = getattr(context.context, 'room_id', 'default')
                    
                    message_data = {
                        "content": content,
                        "user_id": agent.name,  # Use agent name for bot responses
                        "room_id": room_id, 
                        "agent_id": agent.name,
                        "metadata": {
                            "role": "assistant",
                            "timestamp": datetime.now().isoformat(),
                            "client": self.client
                        }
                    }
                    
                    # Store message and capture the result
                    memory_id = await agent.store_message(message_data)
                    
                    # Only log success if we get a valid ID back
                    if memory_id:
                        logger.info(f"[{self.client}] Response stored in agent memory system with ID: {memory_id}")
                    else:
                        logger.error(f"[{self.client}] Failed to store response in memory system - returned None")
                except Exception as e:
                    logger.error(f"[{self.client}] Error storing response in memory system: {e}")
                    import traceback
                    logger.error(f"[{self.client}] Traceback: {traceback.format_exc()}")
            else:
                logger.warning(f"[{self.client}] Agent doesn't have memory system or store_message method")
        else:
            # Log that we couldn't extract content
            logger.warning(f"[{self.client}] Could not extract content from output to store")
            logger.debug(f"[{self.client}] Output representation: {repr(output)}")


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
        # Set room ID for organizing conversations
        room_id = str(message.channel.id)
        
        # Store user message in memory
        if hasattr(agent, 'memory_system') and agent.memory_system and hasattr(agent, 'store_message'):
            try:
                message_content = {"text": content}
                message_data = {
                    "content": message_content,
                    "user_id": str(message.author.id),
                    "room_id": room_id,
                    "agent_id": agent.name,
                    "metadata": {
                        "role": "user",
                        "username": message.author.display_name,
                        "timestamp": str(message.created_at),
                        "client": "Discord"
                    }
                }
                memory_id = await agent.store_message(message_data)
                if memory_id:
                    logger.info(f"[Discord] Message stored in agent memory system with ID: {memory_id}")
                else:
                    logger.warning(f"[Discord] Failed to store message in memory system")
                    # Fall back to legacy memory
                    memory.conversation_history.append({
                        "role": "user",
                        "content": content,
                        "user_id": str(message.author.id),
                        "username": message.author.display_name,
                        "timestamp": str(message.created_at),
                        "client": "Discord"
                    })
                
                # If using new memory, store room_id in context for later use
                if not hasattr(memory, 'room_id'):
                    memory.room_id = room_id
            except Exception as e:
                logger.error(f"[Discord] Error storing message in memory system: {e}")
                # Fall back to legacy memory
                memory.conversation_history.append({
                    "role": "user",
                    "content": content,
                    "user_id": str(message.author.id),
                    "username": message.author.display_name,
                    "timestamp": str(message.created_at),
                    "client": "Discord"
                })
        else:
            # Legacy memory system
            memory.conversation_history.append({
                "role": "user",
                "content": content,
                "user_id": str(message.author.id),
                "username": message.author.display_name,
                "timestamp": str(message.created_at),
                "client": "Discord"
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
                
                # Split response into chunks if necessary
                max_length = 2000
                response_chunks = [response[i:i+max_length] for i in range(0, len(response), max_length)]
                
                # Send each chunk to Discord
                for chunk in response_chunks:
                    await message.channel.send(chunk)
                
                # Log the agent's response
                logger.info(f"[Discord] Agent {agent.name} response: {response}\n")
                
                # Update input items for future context
                return result.to_input_list()
            
            except Exception as e:
                logger.error(f"[Discord] Error processing message: {e}")
                await message.channel.send(f"I encountered an error while processing your message. Please try again later.")
