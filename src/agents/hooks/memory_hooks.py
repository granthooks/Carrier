"""Hooks for integrating memory system with agent runtime."""

from typing import Any, Optional, Dict, List
import logging

from ..agent import Agent
from ..run import RunContextWrapper, RunHooks
from ..logger import logger

class MemoryContextHooks(RunHooks):
    """Hooks that add conversation history from memory system to agent context."""
    
    def __init__(self, user_id: str, room_id: str, conversation_limit: int = 10):
        """Initialize with user and room IDs.
        
        Args:
            user_id: User ID for retrieving conversation history
            room_id: Room/conversation ID for retrieving conversation history
            conversation_limit: Maximum number of messages to retrieve
        """
        self.user_id = user_id
        self.room_id = room_id
        self.conversation_limit = conversation_limit
        self.conversation_added = False
        
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Called when agent processing begins - add conversation history to system prompt."""
        # Skip if memory has already been added to avoid adding it multiple times in a single run
        if self.conversation_added:
            return
            
        try:
            # Check if agent has memory system initialized
            if hasattr(agent, 'memory_system') and agent.memory_system:
                # Format conversation history for context
                conversation_context = await agent.format_conversation_for_context(
                    user_id=self.user_id,
                    room_id=self.room_id,
                    limit=self.conversation_limit
                )
                
                # Get original system prompt
                original_system_prompt = await agent.get_system_prompt(context)
                
                # Only modify if we have a system prompt
                if original_system_prompt:
                    # Enhance system prompt with conversation history
                    enhanced_prompt = f"{original_system_prompt}\n\n{conversation_context}"
                    
                    # Store the original prompt in case needed later
                    if not hasattr(context.context, '_original_system_prompt'):
                        setattr(context.context, '_original_system_prompt', original_system_prompt)
                    
                    # Override the instructions with the enhanced prompt
                    # This is a bit of a hack but it works because get_system_prompt is called
                    # just before each LLM call
                    original_instructions = agent.instructions
                    agent.instructions = enhanced_prompt
                    
                    # Store original instructions to restore later if needed
                    if not hasattr(context.context, '_original_instructions'):
                        setattr(context.context, '_original_instructions', original_instructions)
                    
                    logger.debug(f"Added conversation history from memory to agent context")
                    self.conversation_added = True
                else:
                    logger.warning("No system prompt available to enhance with conversation history")
            else:
                logger.debug("Agent doesn't have memory system initialized")
        except Exception as e:
            logger.error(f"Error adding conversation history to agent context: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when agent processing completes - restore original instructions if needed."""
        # Restore original instructions if we modified them
        if hasattr(context.context, '_original_instructions'):
            agent.instructions = getattr(context.context, '_original_instructions')
            delattr(context.context, '_original_instructions')
            
        # Reset conversation_added for next run
        self.conversation_added = False 