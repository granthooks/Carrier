"""Specialized memory managers for different memory types."""

from typing import Any, Dict, List, Optional, Union

from ..logger import logger
from .memory_system import MemorySystem


class BaseMemoryManager:
    """Base class for all memory managers."""
    
    def __init__(self, memory_system: MemorySystem):
        """Initialize with a memory system.
        
        Args:
            memory_system: The memory system to use
        """
        self.memory_system = memory_system


class MessageManager(BaseMemoryManager):
    """Manager for conversation messages."""
    
    async def create_memory(self, message: Dict[str, Any]) -> str:
        """Create a new message memory."""
        content = message.get("content", {})
        user_id = message.get("user_id", "unknown")
        room_id = message.get("room_id", "default")
        agent_id = message.get("agent_id", "unknown")
        metadata = message.get("metadata", {})
        
        try:
            memory_id = await self.memory_system.store_memory(
                content=content,
                memory_type="message",
                user_id=user_id,
                room_id=room_id,
                agent_id=agent_id,
                metadata=metadata
            )
            
            if memory_id:
                logger.debug(f"Message memory created with ID: {memory_id}")
                return memory_id
            else:
                logger.error(f"Failed to create message memory - store_memory returned None")
                return None
        except Exception as e:
            logger.error(f"Error creating message memory: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
        
    async def get_conversation(
        self, 
        user_id: str, 
        room_id: str, 
        agent_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent conversation messages.
        
        Args:
            user_id: User ID
            room_id: Room/conversation ID
            agent_id: Agent ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message memories in chronological order
        """
        memories = await self.memory_system.get_memories(
            memory_type="message",
            user_id=user_id,
            room_id=room_id,
            agent_id=agent_id,
            limit=limit,
            ascending=True  # Get in chronological order
        )
        
        return memories
        
    async def search_memories_by_embedding(
        self, 
        embedding: List[float], 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for similar messages by embedding."""
        threshold = params.get("match_threshold", 0.7)
        count = params.get("count", 10)
        user_id = params.get("user_id")
        room_id = params.get("room_id")
        agent_id = params.get("agent_id")
        
        # Use direct SQL query instead of RPC
        try:
            # Build a basic filter query
            query = self.memory_system.supabase.table("memories").eq('type', 'message')
            
            if user_id:
                query = query.eq('user_id', user_id)
            if room_id:
                query = query.eq('room_id', room_id)
            if agent_id:
                query = query.eq('agent_id', agent_id)
            
            # Execute with limit
            query = query.limit(count)
            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []


class DescriptionManager(BaseMemoryManager):
    """Manager for user descriptions."""
    
    async def store_description(
        self, 
        user_id: str, 
        description: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a user description.
        
        Args:
            user_id: User ID
            description: User description text
            metadata: Additional metadata
            
        Returns:
            ID of the created memory
        """
        return await self.memory_system.store_memory(
            content={"text": description},
            memory_type="description",
            user_id=user_id,
            room_id="global",  # Descriptions are global
            agent_id="system",  # System-level memory
            metadata=metadata
        )
        
    async def get_description(self, user_id: str) -> Optional[str]:
        """Get the most recent description for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            User description text if found, None otherwise
        """
        memories = await self.memory_system.get_memories(
            memory_type="description",
            user_id=user_id,
            limit=1
        )
        
        if memories and "content" in memories[0] and "text" in memories[0]["content"]:
            return memories[0]["content"]["text"]
        
        return None


class LoreManager(BaseMemoryManager):
    """Manager for agent lore and background."""
    
    async def store_lore(
        self, 
        agent_id: str, 
        lore: Union[str, Dict[str, Any]], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store agent lore/background information.
        
        Args:
            agent_id: Agent ID
            lore: Lore content (text or structured)
            metadata: Additional metadata
            
        Returns:
            ID of the created memory
        """
        return await self.memory_system.store_memory(
            content=lore,
            memory_type="lore",
            user_id="system",  # System-level memory
            room_id="global",  # Lore is global
            agent_id=agent_id,
            metadata=metadata
        )
        
    async def get_lore(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all lore for an agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of lore memories
        """
        return await self.memory_system.get_memories(
            memory_type="lore",
            agent_id=agent_id
        )


class DocumentsManager(BaseMemoryManager):
    """Manager for large documents."""
    
    async def store_document(
        self, 
        title: str, 
        content: str, 
        user_id: str = "system", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a document.
        
        Args:
            title: Document title
            content: Document content
            user_id: User who created/owns the document
            metadata: Additional metadata
            
        Returns:
            ID of the created memory
        """
        doc_content = {
            "title": title,
            "text": content
        }
        
        return await self.memory_system.store_memory(
            content=doc_content,
            memory_type="document",
            user_id=user_id,
            room_id="global",  # Documents are global
            agent_id="system",  # System-level memory
            metadata=metadata
        )
        
    async def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document memory if found, None otherwise
        """
        return await self.memory_system.get_memory_by_id(document_id)
        
    async def search_documents(
        self, 
        query: str, 
        threshold: float = 0.7, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for documents by content similarity.
        
        Args:
            query: Search query
            threshold: Similarity threshold
            limit: Maximum number of results
            
        Returns:
            List of matching documents with similarity scores
        """
        return await self.memory_system.retrieve_similar(
            query=query,
            threshold=threshold,
            limit=limit,
            memory_type="document"
        )


class KnowledgeManager(BaseMemoryManager):
    """Manager for searchable knowledge fragments."""
    
    async def store_knowledge(
        self, 
        content: str, 
        source: str, 
        agent_id: str = "system", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a knowledge fragment.
        
        Args:
            content: Knowledge content
            source: Source of the knowledge (e.g., document title)
            agent_id: Agent the knowledge is for
            metadata: Additional metadata
            
        Returns:
            ID of the created memory
        """
        knowledge_content = {
            "text": content,
            "source": source
        }
        
        if metadata is None:
            metadata = {}
            
        metadata["source"] = source
        
        return await self.memory_system.store_memory(
            content=knowledge_content,
            memory_type="knowledge",
            user_id="system",  # System-level memory
            room_id="global",  # Knowledge is global
            agent_id=agent_id,
            metadata=metadata
        )
        
    async def search_knowledge(
        self, 
        query: str, 
        agent_id: Optional[str] = None, 
        threshold: float = 0.7, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search knowledge fragments by query similarity.
        
        Args:
            query: Search query
            agent_id: Optional agent ID to filter by
            threshold: Similarity threshold
            limit: Maximum number of results
            
        Returns:
            List of matching knowledge fragments with similarity scores
        """
        return await self.memory_system.retrieve_similar(
            query=query,
            threshold=threshold,
            limit=limit,
            memory_type="knowledge",
            agent_id=agent_id
        )


class RAGKnowledgeManager(BaseMemoryManager):
    """Manager for RAG-based knowledge retrieval."""
    
    async def load_knowledge(
        self, 
        documents: List[Dict[str, Any]], 
        chunk_size: int = 1000, 
        chunk_overlap: int = 200,
        agent_id: str = "system"
    ) -> List[str]:
        """Process and load documents into knowledge base.
        
        Args:
            documents: List of document objects with title and content
            chunk_size: Size of chunks to split documents into
            chunk_overlap: Overlap between chunks
            agent_id: Agent ID to associate the knowledge with
            
        Returns:
            List of created memory IDs
        """
        memory_ids = []
        
        for doc in documents:
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")
            
            # Skip empty documents
            if not content.strip():
                continue
                
            # Simple chunking - could be enhanced with semantic chunking
            chunks = self._chunk_text(content, chunk_size, chunk_overlap)
            
            for i, chunk in enumerate(chunks):
                metadata = {
                    "document_title": title,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                
                memory_id = await self.memory_system.store_memory(
                    content={"text": chunk, "source": title},
                    memory_type="rag_knowledge",
                    user_id="system",  # System-level memory
                    room_id="global",  # Knowledge is global
                    agent_id=agent_id,
                    metadata=metadata
                )
                
                memory_ids.append(memory_id)
                
        return memory_ids
        
    def _chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Split text into overlapping chunks.
        
        Args:
            text: Text to split
            chunk_size: Size of chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # Adjust to avoid splitting in the middle of a word
            if end < len(text) and not text[end].isspace():
                # Look for the last space within the chunk
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
                    
            chunks.append(text[start:end].strip())
            start = end - chunk_overlap
            
        return chunks
        
    async def search(
        self, 
        query: str, 
        agent_id: Optional[str] = None, 
        max_results: int = 5, 
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search RAG knowledge base for relevant context.
        
        Args:
            query: Search query
            agent_id: Optional agent ID to filter by
            max_results: Maximum number of results
            min_score: Minimum similarity score
            
        Returns:
            List of matching knowledge chunks with similarity scores
        """
        results = await self.memory_system.retrieve_similar(
            query=query,
            threshold=min_score,
            limit=max_results,
            memory_type="rag_knowledge",
            agent_id=agent_id
        )
        
        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        return results
        
    async def get_knowledge_context(
        self, 
        query: str, 
        agent_id: Optional[str] = None, 
        max_tokens: int = 2000
    ) -> str:
        """Get contextual information for a query.
        
        Args:
            query: Query to get context for
            agent_id: Optional agent ID to filter by
            max_tokens: Approximate maximum tokens to return
            
        Returns:
            Formatted context string with relevant knowledge
        """
        results = await self.search(
            query=query,
            agent_id=agent_id,
            max_results=10,  # Get more results than needed to have options
            min_score=0.6  # Lower threshold for more results
        )
        
        if not results:
            return "No relevant information found."
            
        # Build context string
        context_parts = []
        total_length = 0
        char_per_token = 4  # Rough approximation
        max_chars = max_tokens * char_per_token
        
        for result in results:
            content = result.get("content", {})
            text = content.get("text", "")
            source = content.get("source", "Unknown")
            
            # Skip if this would exceed max_chars
            if total_length + len(text) > max_chars:
                break
                
            context_parts.append(f"Source: {source}\n{text}\n---")
            total_length += len(text) + len(source) + 8  # 8 chars for formatting
            
        return "\n".join(context_parts)
