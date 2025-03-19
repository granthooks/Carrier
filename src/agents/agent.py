from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Generic, Optional, cast, List, Dict

from . import _utils
from ._utils import MaybeAwaitable
from .guardrail import InputGuardrail, OutputGuardrail
from .handoffs import Handoff
from .items import ItemHelpers
from .logger import logger
from .model_settings import ModelSettings
from .models.interface import Model
from .run_context import RunContextWrapper, TContext
from .tool import Tool, function_tool

if TYPE_CHECKING:
    from .lifecycle import AgentHooks
    from .result import RunResult
    from .memory import MemorySystem, MessageManager, DescriptionManager, LoreManager, DocumentsManager, KnowledgeManager, RAGKnowledgeManager


@dataclass
class Agent(Generic[TContext]):
    """An agent is an AI model configured with instructions, tools, guardrails, handoffs and more.

    We strongly recommend passing `instructions`, which is the "system prompt" for the agent. In
    addition, you can pass `description`, which is a human-readable description of the agent, used
    when the agent is used inside tools/handoffs.

    Agents are generic on the context type. The context is a (mutable) object you create. It is
    passed to tool functions, handoffs, guardrails, etc.
    """

    name: str
    """The name of the agent."""

    instructions: (
        str
        | Callable[
            [RunContextWrapper[TContext], Agent[TContext]],
            MaybeAwaitable[str],
        ]
        | None
    ) = None
    """The instructions for the agent. Will be used as the "system prompt" when this agent is
    invoked. Describes what the agent should do, and how it responds.

    Can either be a string, or a function that dynamically generates instructions for the agent. If
    you provide a function, it will be called with the context and the agent instance. It must
    return a string.
    """

    handoff_description: str | None = None
    """A description of the agent. This is used when the agent is used as a handoff, so that an
    LLM knows what it does and when to invoke it.
    """

    handoffs: list[Agent[Any] | Handoff[TContext]] = field(default_factory=list)
    """Handoffs are sub-agents that the agent can delegate to. You can provide a list of handoffs,
    and the agent can choose to delegate to them if relevant. Allows for separation of concerns and
    modularity.
    """

    model: str | Model | None = None
    """The model implementation to use when invoking the LLM.

    By default, if not set, the agent will use the default model configured in
    `model_settings.DEFAULT_MODEL`.
    """

    model_settings: ModelSettings = field(default_factory=ModelSettings)
    """Configures model-specific tuning parameters (e.g. temperature, top_p).
    """

    tools: list[Tool] = field(default_factory=list)
    """A list of tools that the agent can use."""

    input_guardrails: list[InputGuardrail[TContext]] = field(default_factory=list)
    """A list of checks that run in parallel to the agent's execution, before generating a
    response. Runs only if the agent is the first agent in the chain.
    """

    output_guardrails: list[OutputGuardrail[TContext]] = field(default_factory=list)
    """A list of checks that run on the final output of the agent, after generating a response.
    Runs only if the agent produces a final output.
    """

    output_type: type[Any] | None = None
    """The type of the output object. If not provided, the output will be `str`."""

    hooks: AgentHooks[TContext] | None = None
    """A class that receives callbacks on various lifecycle events for this agent.
    """
    
    # Memory system components
    memory_system: Any = None
    """The memory system for the agent to store and retrieve memories."""
    
    message_manager: Any = None
    """Manager for conversation messages."""
    
    description_manager: Any = None
    """Manager for user descriptions."""
    
    lore_manager: Any = None
    """Manager for agent lore and background information."""
    
    documents_manager: Any = None
    """Manager for large documents."""
    
    knowledge_manager: Any = None
    """Manager for searchable knowledge fragments."""
    
    rag_knowledge_manager: Any = None
    """Manager for RAG-based knowledge retrieval."""

    def __post_init__(self):
        """Initialize memory system components if needed."""
        # Import here to avoid circular imports
        try:
            from .memory import MemorySystem, MessageManager, DescriptionManager, LoreManager
            from .memory import DocumentsManager, KnowledgeManager, RAGKnowledgeManager
            
            if self.memory_system is None:
                # Initialize with default configuration
                self.memory_system = MemorySystem()
                
            if self.message_manager is None and self.memory_system is not None:
                # Initialize message manager with memory system
                self.message_manager = MessageManager(self.memory_system)
                
            if self.description_manager is None and self.memory_system is not None:
                # Initialize description manager with memory system
                self.description_manager = DescriptionManager(self.memory_system)
                
            if self.lore_manager is None and self.memory_system is not None:
                # Initialize lore manager with memory system
                self.lore_manager = LoreManager(self.memory_system)
                
            if self.documents_manager is None and self.memory_system is not None:
                # Initialize documents manager with memory system
                self.documents_manager = DocumentsManager(self.memory_system)
                
            if self.knowledge_manager is None and self.memory_system is not None:
                # Initialize knowledge manager with memory system
                self.knowledge_manager = KnowledgeManager(self.memory_system)
                
            if self.rag_knowledge_manager is None and self.memory_system is not None:
                # Initialize RAG knowledge manager with memory system
                self.rag_knowledge_manager = RAGKnowledgeManager(self.memory_system)
        except ImportError:
            # Memory system not available, skip initialization
            logger.debug("Memory system not available, skipping memory initialization")
    
    def clone(self, **kwargs: Any) -> Agent[TContext]:
        """Make a copy of the agent, with the given arguments changed. For example, you could do:
        ```
        new_agent = agent.clone(instructions="New instructions")
        ```
        """
        return dataclasses.replace(self, **kwargs)

    def as_tool(
        self,
        tool_name: str | None,
        tool_description: str | None,
        custom_output_extractor: Callable[[RunResult], Awaitable[str]] | None = None,
    ) -> Tool:
        """Transform this agent into a tool, callable by other agents.

        This is different from handoffs in two ways:
        1. In handoffs, the new agent receives the conversation history. In this tool, the new agent
           receives generated input.
        2. In handoffs, the new agent takes over the conversation. In this tool, the new agent is
           called as a tool, and the conversation is continued by the original agent.

        Args:
            tool_name: The name of the tool. If not provided, the agent's name will be used.
            tool_description: The description of the tool, which should indicate what it does and
                when to use it.
            custom_output_extractor: A function that extracts the output from the agent. If not
                provided, the last message from the agent will be used.
        """

        @function_tool(
            name_override=tool_name or _utils.transform_string_function_style(self.name),
            description_override=tool_description or "",
        )
        async def run_agent(context: RunContextWrapper, input: str) -> str:
            from .run import Runner

            output = await Runner.run(
                starting_agent=self,
                input=input,
                context=context.context,
            )
            if custom_output_extractor:
                return await custom_output_extractor(output)

            return ItemHelpers.text_message_outputs(output.new_items)

        return run_agent

    async def get_system_prompt(self, run_context: RunContextWrapper[TContext]) -> str | None:
        """Get the system prompt for the agent."""
        if isinstance(self.instructions, str):
            return self.instructions
        elif callable(self.instructions):
            if inspect.iscoroutinefunction(self.instructions):
                return await cast(Awaitable[str], self.instructions(run_context, self))
            else:
                return cast(str, self.instructions(run_context, self))
        elif self.instructions is not None:
            logger.error(f"Instructions must be a string or a function, got {self.instructions}")

        return None
        
    # Memory system methods
    
    async def store_message(self, message: Dict[str, Any]) -> Optional[str]:
        """Store a message in the memory system.
        
        Args:
            message: Message data including content, user_id, room_id, etc.
            
        Returns:
            Memory ID if successful, None otherwise
        """
        if self.message_manager is None:
            logger.warning("No message manager available for agent")
            return None
            
        try:
            return await self.message_manager.create_memory(message)
        except Exception as e:
            logger.error(f"Failed to store message in memory system: {e}")
            return None
        
    async def get_conversation(
        self, 
        user_id: str, 
        room_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent conversation for the agent.
        
        Args:
            user_id: User ID
            room_id: Room/conversation ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message memories in chronological order
        """
        if self.message_manager is None:
            logger.warning("No message manager available for agent")
            return []
            
        return await self.message_manager.get_conversation(
            user_id=user_id,
            room_id=room_id,
            agent_id=self.name,
            limit=limit
        )
        
    async def find_similar_messages(
        self, 
        query: str, 
        threshold: float = 0.7, 
        limit: int = 10,
        user_id: Optional[str] = None,
        room_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find messages similar to the query.
        
        Args:
            query: Query text
            threshold: Similarity threshold
            limit: Maximum number of results
            user_id: Optional filter by user ID
            room_id: Optional filter by room ID
            
        Returns:
            List of similar message memories with similarity scores
        """
        if self.memory_system is None or self.message_manager is None:
            logger.warning("No memory system available for agent")
            return []
            
        # Generate embedding for query (now synchronous)
        embedding = self.memory_system.embed(query)
        
        # Search for similar messages
        params = {
            "match_threshold": threshold,
            "count": limit,
            "agent_id": self.name
        }
        
        if user_id:
            params["user_id"] = user_id
        if room_id:
            params["room_id"] = room_id
            
        return await self.message_manager.search_memories_by_embedding(
            embedding=embedding,
            params=params
        )
        
    async def store_user_description(
        self, 
        user_id: str, 
        description: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Store a user description.
        
        Args:
            user_id: User ID
            description: User description text
            metadata: Additional metadata
            
        Returns:
            Memory ID if successful, None otherwise
        """
        if self.description_manager is None:
            logger.warning("No description manager available for agent")
            return None
            
        return await self.description_manager.store_description(
            user_id=user_id,
            description=description,
            metadata=metadata
        )
        
    async def get_user_description(self, user_id: str) -> Optional[str]:
        """Get the most recent description for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            User description text if found, None otherwise
        """
        if self.description_manager is None:
            logger.warning("No description manager available for agent")
            return None
            
        return await self.description_manager.get_description(user_id)
        
    async def store_lore(
        self, 
        lore: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Store agent lore/background information.
        
        Args:
            lore: Lore content
            metadata: Additional metadata
            
        Returns:
            Memory ID if successful, None otherwise
        """
        if self.lore_manager is None:
            logger.warning("No lore manager available for agent")
            return None
            
        return await self.lore_manager.store_lore(
            agent_id=self.name,
            lore=lore,
            metadata=metadata
        )
        
    async def get_lore(self) -> List[Dict[str, Any]]:
        """Get all lore for the agent.
        
        Returns:
            List of lore memories
        """
        if self.lore_manager is None:
            logger.warning("No lore manager available for agent")
            return []
            
        return await self.lore_manager.get_lore(self.name)
        
    async def get_knowledge_context(
        self, 
        query: str, 
        max_tokens: int = 2000
    ) -> str:
        """Get knowledge context for a query using RAG.
        
        Args:
            query: Query to get context for
            max_tokens: Approximate maximum tokens to return
            
        Returns:
            Formatted context string with relevant knowledge
        """
        if self.rag_knowledge_manager is None:
            logger.warning("No RAG knowledge manager available for agent")
            return "No knowledge context available."
            
        return await self.rag_knowledge_manager.get_knowledge_context(
            query=query,
            agent_id=self.name,
            max_tokens=max_tokens
        )


# Legacy AgentMemory for backward compatibility
@dataclass
class AgentMemory:
    """Maintains the agent's memory between interactions (Legacy)"""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_info: Dict[str, Any] = field(default_factory=dict)
    last_topics: List[str] = field(default_factory=list)
    client: str = "generic"  # Track which client the conversation is from
