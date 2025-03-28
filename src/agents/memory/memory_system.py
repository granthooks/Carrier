"""Core memory system for Carrier agents."""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import openai
from supabase import Client, create_client
from dotenv import load_dotenv

from ..logger import logger
from .cache import MemoryCache


class MemorySystem:
    """Central memory system for agent interactions using Supabase and OpenAI embeddings."""
    
    def __init__(
        self, 
        supabase_url: str = None, 
        supabase_key: str = None,
        embedding_model: str = "text-embedding-ada-002",
        schema_name: str = "public"
    ):
        """Initialize memory system with Supabase connection.
        
        Args:
            supabase_url: URL of the Supabase instance (defaults to SUPABASE_URL env var)
            supabase_key: API key for the Supabase instance (defaults to SUPABASE_SERVICE_ROLE_KEY env var)
            embedding_model: OpenAI embedding model to use
            schema_name: Schema name for memory tables
        """
        # Ensure dotenv is loaded
        load_dotenv()
        
        # Get credentials from environment if not provided
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Supabase credentials required. Either provide them directly or set "
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables."
            )
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.embedding_model = embedding_model
        self.schema_name = schema_name
        self.cache = MemoryCache()
        
        # Initialize the schema
        self._ensure_schema()
        
    def _ensure_schema(self) -> None:
        """Ensure the memory table exists."""
        try:
            # Just try to access the table to check if it exists
            try:
                # Use the public schema
                result = self.supabase.table("memories").select("id").limit(1).execute()
                logger.info("Successfully connected to memories table")
                return
            except Exception as table_error:
                error_str = str(table_error)
                logger.error(f"Could not access memory table: {error_str}")
                
                if "does not exist" in error_str:
                    logger.error("The table 'memories' does not exist.")
                    logger.error("Please run the setup SQL to create the necessary table.")
                    raise RuntimeError(
                        "Table 'memories' doesn't exist. "
                        "Please run the setup SQL script."
                    )
                else:
                    raise table_error
        except Exception as e:
            logger.error(f"Error checking memory table: {e}")
            raise
        
    def embed(self, text: str) -> List[float]:
        """Generate embeddings for the given text.
        
        Args:
            text: Text to generate embeddings for
            
        Returns:
            List of embedding vector values
        """
        cache_key = f"embed:{hash(text)}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
            
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text)
            
        # Better error handling for API calls    
        try:
            # Use the new OpenAI client format for embeddings (synchronous)
            import openai
            
            client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
            logger.debug(f"Created OpenAI client with model {self.embedding_model}")
            
            # Generate embedding with the new API format (no await)
            response = client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            
            # Extract the embedding from the response
            if hasattr(response, 'data') and len(response.data) > 0:
                embedding = response.data[0].embedding
                self.cache.set(cache_key, embedding)
                return embedding
            else:
                logger.error(f"Unexpected response format from OpenAI: {response}")
                return [0.0] * 1536  # Fallback to zero vector
            
        except Exception as e:
            import traceback
            logger.error(f"Error generating embedding: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return zero vector as fallback (1536 is OpenAI's default dimension)
            return [0.0] * 1536
        
    async def store_memory(
        self, 
        content: Union[str, Dict[str, Any]], 
        memory_type: str, 
        user_id: str, 
        room_id: str, 
        agent_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a memory with embedding in Supabase."""
        memory_id = str(uuid.uuid4())
        
        # Convert string content to dict if needed
        if isinstance(content, str):
            content_dict = {"text": content}
        else:
            content_dict = content
        
        # Generate JSON representation for embedding
        if isinstance(content_dict, dict) and "text" in content_dict:
            embed_text = content_dict["text"]
        else:
            embed_text = json.dumps(content_dict)
        
        try:
            # Generate embedding
            embedding = self.embed(embed_text)
            
            # Prepare memory object
            memory = {
                "id": memory_id,
                "type": memory_type,
                "content": content_dict,
                "embedding": embedding,
                "user_id": user_id,
                "room_id": room_id,
                "agent_id": agent_id,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }
            
            # Store in Supabase
            logger.debug(f"Inserting memory into table: memories")
            logger.debug(f"Memory object: {json.dumps({**memory, 'embedding': '[vector]'}, default=str)}")
            
            try:
                # Insert the memory
                result = self.supabase.table("memories").insert(memory).execute()
                
                # Log the result data to check what's being returned
                logger.debug(f"Insert result: {result.data if hasattr(result, 'data') else result}")
                
                # Verify the insertion
                verification = self.supabase.table("memories").select("*").eq("id", memory_id).execute()
                if verification and verification.data and len(verification.data) > 0:
                    logger.debug(f"Memory verified in database")
                else:
                    logger.warning(f"Memory not found after insertion")
                
                return memory_id
            except Exception as insert_error:
                logger.error(f"Error inserting memory: {insert_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return None
        except Exception as e:
            logger.error(f"Error in store_memory: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
        
    async def retrieve_similar(
        self, 
        query: str, 
        threshold: float = 0.7, 
        limit: int = 10, 
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None,
        room_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve similar memories using vector search.
        
        Args:
            query: Query text to find similar memories
            threshold: Similarity threshold (0-1)
            limit: Maximum number of results
            memory_type: Optional filter by memory type
            user_id: Optional filter by user ID
            room_id: Optional filter by room ID
            agent_id: Optional filter by agent ID
            embedding: Optional pre-computed embedding vector
            
        Returns:
            List of memory objects with similarity scores
        """
        # Generate embedding for query if not provided
        query_embedding = embedding if embedding is not None else self.embed(query)
        
        try:
            # Build the query
            rpc_query = self.supabase.rpc(
                'match_memories',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_count': limit,
                    'schema_name': self.schema_name
                }
            )
            
            # Add filters if provided
            if memory_type:
                rpc_query = rpc_query.eq('type', memory_type)
            if user_id:
                rpc_query = rpc_query.eq('user_id', user_id)
            if room_id:
                rpc_query = rpc_query.eq('room_id', room_id)
            if agent_id:
                rpc_query = rpc_query.eq('agent_id', agent_id)
                
            # Execute query
            result = rpc_query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Error retrieving similar memories: {e}")
            return []
            
    async def get_memories(
        self,
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None,
        room_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20,
        order_by: str = "created_at",
        ascending: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieve memories based on filters.
        
        Args:
            memory_type: Optional filter by memory type
            user_id: Optional filter by user ID
            room_id: Optional filter by room ID
            agent_id: Optional filter by agent ID
            limit: Maximum number of results
            order_by: Field to order results by
            ascending: Whether to sort in ascending order
            
        Returns:
            List of memory objects
        """
        try:
            # Build the query with filters as parameters
            query = self.supabase.from_("memories").select("*")
            
            # Add filters
            if memory_type:
                query = query.eq("type", memory_type)
            if user_id:
                query = query.eq("user_id", user_id)
            if room_id:
                query = query.eq("room_id", room_id)
            if agent_id:
                query = query.eq("agent_id", agent_id)
                
            # Add ordering - use the correct syntax for the Supabase client
            # Instead of using ascending as a parameter, use separate methods
            if ascending:
                query = query.order(order_by)  # Ascending order is default
            else:
                query = query.order(order_by, desc=True)  # Use desc=True for descending
            
            # Add limit
            query = query.limit(limit)
            
            # Execute
            result = query.execute()
            return result.data
        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
            
    async def delete_memories(
        self,
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None,
        room_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        older_than: Optional[str] = None
    ) -> int:
        """Delete memories based on filters.
        
        Args:
            memory_type: Optional filter by memory type
            user_id: Optional filter by user ID
            room_id: Optional filter by room ID
            agent_id: Optional filter by agent ID
            older_than: ISO format datetime string, delete memories older than this
            
        Returns:
            Number of memories deleted
        """
        try:
            query = self.supabase.from_("memories").schema(self.schema_name).delete()
            
            # Add filters
            if memory_type:
                query = query.eq("type", memory_type)
            if user_id:
                query = query.eq("user_id", user_id)
            if room_id:
                query = query.eq("room_id", room_id)
            if agent_id:
                query = query.eq("agent_id", agent_id)
            if older_than:
                query = query.lt("created_at", older_than)
                
            # Execute
            result = query.execute()
            return len(result.data)
        except Exception as e:
            logger.error(f"Error deleting memories: {e}")
            return 0
    
    async def get_memory_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific memory by ID.
        
        Args:
            memory_id: ID of the memory to retrieve
            
        Returns:
            Memory object if found, None otherwise
        """
        try:
            result = self.supabase.from_("memories").schema(self.schema_name).select("*").eq("id", memory_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error retrieving memory by ID: {e}")
            return None
