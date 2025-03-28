"""
Hooks for integrating memory system with agent runtime.
"""

from typing import Any, Optional, Dict, List
import logging

from agents import RunContextWrapper, RunHooks, Agent

from ..extensions.carrier_agent import AgentMemory


class MemoryContextHooks(RunHooks):
    """Hooks that add conversation history from memory system to agent context."""

    def __init__(self, user_id: str, room_id: str, conversation_limit: int = 10, client_name: str = "generic"):
        """Initialize with user and room IDs.

        Args:
            user_id: User ID for retrieving conversation history
            room_id: Room/conversation ID for retrieving conversation history
            conversation_limit: Maximum number of messages to retrieve
            client_name: Name of the client (discord, instagram, etc.)
        """
        self.user_id = user_id
        self.room_id = room_id
        self.conversation_limit = conversation_limit
        self.conversation_added = False
        self.client_name = client_name

    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Called when agent processing begins - add conversation history to system prompt."""
        # Skip if memory has already been added to avoid adding it multiple times in a single run
        if self.conversation_added:
            return

        # Only process if context contains a memory object
        memory = self._get_memory_from_context(context)
        if not memory:
            return

        # Add conversation history to system prompt
        if hasattr(memory, 'conversation_history') and memory.conversation_history:
            # Format the conversation history for context
            formatted_history = self.format_conversation_for_context(memory.conversation_history)
            
            # Only add if there's actual content
            if formatted_history:
                # Add to system prompt
                system_prompt = agent.instructions + "\n\n## Recent Conversation History\n" + formatted_history
                agent.instructions = system_prompt
                
                # Mark as added to avoid adding it again in the same run
                self.conversation_added = True

    def _get_memory_from_context(self, context: RunContextWrapper) -> Optional[AgentMemory]:
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

    def format_conversation_for_context(self, history: List[Dict[str, Any]]) -> str:
        """Format conversation history for inclusion in system prompt."""
        if not history:
            return ""
            
        # Limit to most recent messages
        recent_history = history[-self.conversation_limit:]
        
        # Format each message
        formatted_messages = []
        for message in recent_history:
            role = message.get('role', '')
            content = message.get('content', '')
            timestamp = message.get('timestamp', '')
            
            # Only add if we have both role and content
            if role and content:
                formatted_messages.append(f"{role.capitalize()}: {content}")
                
        # Join with line breaks
        return "\n".join(formatted_messages)

    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when agent processing completes."""
        # Reset conversation_added flag at the end of the run
        self.conversation_added = False
