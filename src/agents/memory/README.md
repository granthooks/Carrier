# Carrier Memory System

A robust memory system for Carrier agents, using Supabase as the backend for storage and OpenAI embeddings for semantic search capabilities.

## Overview

The Carrier Memory System provides agents with advanced memory capabilities including:

- Vector-based memory retrieval using embeddings
- Persistent storage across agent restarts
- Multiple memory types for different use cases
- Retrieval-augmented generation (RAG) support
- Integrated caching for performance
- Command-line tools for management

## Architecture

The memory system consists of the following components:

1. **MemorySystem**: The core class that handles Supabase interaction and embedding generation
2. **Memory Managers**: Specialized classes for different memory types
3. **MemoryCache**: LRU cache with TTL support for performance optimization
4. **Database Schema**: Supabase tables with vector support for similarity search
5. **CLI Tool**: Command-line interface for memory management

## Getting Started

### Prerequisites

- Supabase instance running (defaults to https://localhost:8000)
- OpenAI API key for embeddings
- Python 3.9+

### Initializing the Database

Run the memory CLI tool to initialize the database schema:

```bash
python -m src.tools.memory_cli init
```

### Basic Usage

```python
from agents.memory import MemorySystem, MessageManager

# Create a memory system
memory_system = MemorySystem(
    supabase_url="https://localhost:8000",
    supabase_key="your-api-key"
)

# Create a message manager
message_manager = MessageManager(memory_system)

# Store a message
message_id = await message_manager.create_memory({
    "content": {"text": "Hello, how can I help you?"},
    "user_id": "user123",
    "room_id": "room456",
    "agent_id": "assistant",
    "metadata": {"role": "assistant"}
})

# Get conversation history
messages = await message_manager.get_conversation(
    user_id="user123",
    room_id="room456",
    agent_id="assistant",
    limit=10
)

# Search for similar messages
results = await memory_system.retrieve_similar(
    query="How can you help me?",
    threshold=0.7,
    limit=5,
    memory_type="message"
)
```

## Agent Integration

The memory system is integrated directly into the Agent class. When an agent is created, the memory system components are automatically initialized if they aren't provided.

```python
from agents import Agent

# Create an agent with default memory system
agent = Agent(name="assistant")

# The agent now has access to all memory system functionality
await agent.store_message({
    "content": {"text": "Hello!"},
    "user_id": "user123",
    "room_id": "room456",
    "agent_id": "assistant"
})

# Retrieve conversation
conversation = await agent.get_conversation(
    user_id="user123",
    room_id="room456"
)

# Find similar messages
similar = await agent.find_similar_messages(
    query="What was our conversation about?",
    threshold=0.7
)

# Get knowledge context for RAG
context = await agent.get_knowledge_context(
    query="Tell me about machine learning"
)
```

## Memory Types

The system supports multiple types of memories:

1. **Messages**: Conversation messages between users and agents
2. **Descriptions**: User descriptions and profiles
3. **Lore**: Agent background information
4. **Documents**: Large documents for knowledge retrieval
5. **Knowledge**: Searchable knowledge fragments
6. **RAG Knowledge**: Chunked and indexed documents for RAG

## CLI Tool

The memory CLI tool provides functionality for managing memories:

```bash
# List memories for an agent
python -m src.tools.memory_cli list --agent assistant --format

# Clear memories for an agent
python -m src.tools.memory_cli clear assistant

# Test similarity search
python -m src.tools.memory_cli similar "How can I help you?"

# Initialize database schema
python -m src.tools.memory_cli init
```

## Database Schema

The memory system uses the following database schema:

```sql
CREATE TABLE carrier_memory.memories (
  id UUID PRIMARY KEY,
  type TEXT NOT NULL,
  content JSONB NOT NULL,
  embedding vector(1536),
  user_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TABLE carrier_memory.relationships (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  interaction_count INTEGER DEFAULT 0,
  sentiment_score FLOAT,
  metadata JSONB DEFAULT '{}'::jsonb,
  last_interaction TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

## Advanced Usage

### RAG Knowledge Management

```python
# Load documents into RAG knowledge base
documents = [
    {"title": "Introduction to ML", "content": "Machine learning is..."},
    {"title": "Neural Networks", "content": "Neural networks are..."}
]

memory_ids = await agent.rag_knowledge_manager.load_knowledge(
    documents=documents,
    chunk_size=1000,
    chunk_overlap=200
)

# Get contextual information for a query
context = await agent.get_knowledge_context(
    query="Explain neural networks",
    max_tokens=2000
)
```

### User Description Management

```python
# Store a user description
await agent.store_user_description(
    user_id="user123",
    description="John is a 35-year-old software engineer interested in AI."
)

# Get user description
description = await agent.get_user_description(user_id="user123")
```

### Agent Lore Management

```python
# Store agent lore
await agent.store_lore(
    lore="Assistant is a helpful AI designed to answer questions about technology."
)

# Get agent lore
lore = await agent.get_lore()
