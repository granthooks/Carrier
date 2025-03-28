"""
Utility functions for working with agent hooks.
"""

from typing import Optional, Type, Any

from agents import Agent, RunHooks

from ..hooks.memory_hooks import MemoryContextHooks
from ..extensions.carrieragent import AgentMemory


def add_memory_hooks(
    base_hooks_class: Type[RunHooks],
    agent: Agent,
    user_id: str,
    room_id: str,
    conversation_limit: int = 10,
    client_name: str = "generic"
) -> RunHooks:
    """
    Create a composite hooks object that includes memory context hooks.
    
    Args:
        base_hooks_class: Base hooks class to extend (Discord, Instagram, etc.)
        agent: Agent to use
        user_id: User ID for memory context
        room_id: Room ID for memory context
        conversation_limit: Maximum number of conversation messages to include
        client_name: Name of the client (discord, instagram, etc.)
        
    Returns:
        Composite hooks object with memory context hooks
    """
    # Create memory hooks
    memory_hooks = MemoryContextHooks(
        user_id=user_id,
        room_id=room_id,
        conversation_limit=conversation_limit,
        client_name=client_name
    )
    
    # Create base hooks instance
    base_hooks = base_hooks_class()
    
    # Create composite hooks class that combines both
    class CompositeHooks(RunHooks):
        """Composite hooks that combine memory hooks with client-specific hooks."""
        
        async def on_agent_start(self, context: Any, agent: Agent) -> None:
            """Called when agent processing begins."""
            # First call base hooks
            if hasattr(base_hooks, 'on_agent_start'):
                await base_hooks.on_agent_start(context, agent)
                
            # Then memory hooks
            await memory_hooks.on_agent_start(context, agent)
        
        async def on_tool_start(self, context: Any, agent: Agent, tool: Any) -> None:
            """Called when a tool execution begins."""
            if hasattr(base_hooks, 'on_tool_start'):
                await base_hooks.on_tool_start(context, agent, tool)
        
        async def on_tool_end(self, context: Any, agent: Agent, tool: Any, result: str) -> None:
            """Called when a tool execution completes."""
            if hasattr(base_hooks, 'on_tool_end'):
                await base_hooks.on_tool_end(context, agent, tool, result)
        
        async def on_agent_end(self, context: Any, agent: Agent, output: Any) -> None:
            """Called when agent processing completes."""
            # First call base hooks
            if hasattr(base_hooks, 'on_agent_end'):
                await base_hooks.on_agent_end(context, agent, output)
                
            # Then memory hooks
            await memory_hooks.on_agent_end(context, agent, output)
    
    return CompositeHooks()
