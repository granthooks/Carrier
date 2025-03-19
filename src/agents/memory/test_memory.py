#!/usr/bin/env python3
"""
Test script for the Carrier Memory System.

This script demonstrates basic memory system functionality, 
including storing and retrieving memories and semantic search.
"""

import asyncio
import os
import json
import sys
from datetime import datetime
from typing import Dict, List, Any

# Add the project root to the path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.agents.memory import MemorySystem, MessageManager, RAGKnowledgeManager


async def test_basic_memory():
    """Test basic memory operations."""
    print("\n===== Testing Basic Memory Operations =====")
    
    # Initialize memory system
    memory_system = MemorySystem()
    message_manager = MessageManager(memory_system)
    
    # Generate a unique user and room ID for testing
    test_id = datetime.now().strftime("%Y%m%d%H%M%S")
    user_id = f"test_user_{test_id}"
    room_id = f"test_room_{test_id}"
    agent_id = "test_agent"
    
    print(f"Creating test conversation with user_id={user_id}, room_id={room_id}")
    
    # Store a user message
    user_message = {
        "content": {"text": "Hello, can you help me with Python programming?"},
        "user_id": user_id,
        "room_id": room_id,
        "agent_id": agent_id,
        "metadata": {
            "role": "user",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    user_message_id = await message_manager.create_memory(user_message)
    print(f"Stored user message with ID: {user_message_id}")
    
    # Store an agent response
    agent_message = {
        "content": {"text": "Yes, I'd be happy to help with Python programming! What specific questions do you have?"},
        "user_id": agent_id,
        "room_id": room_id,
        "agent_id": agent_id,
        "metadata": {
            "role": "assistant",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    agent_message_id = await message_manager.create_memory(agent_message)
    print(f"Stored agent message with ID: {agent_message_id}")
    
    # Retrieve conversation
    conversation = await message_manager.get_conversation(
        user_id=user_id,
        room_id=room_id,
        agent_id=agent_id
    )
    
    print(f"\nRetrieved conversation ({len(conversation)} messages):")
    for i, message in enumerate(conversation):
        role = message.get("metadata", {}).get("role", "unknown")
        content_text = message.get("content", {}).get("text", "")
        print(f"  {i+1}. [{role}]: {content_text}")


async def test_semantic_search():
    """Test semantic search functionality."""
    print("\n===== Testing Semantic Search =====")
    
    # Initialize memory system
    memory_system = MemorySystem()
    message_manager = MessageManager(memory_system)
    
    # Generate a unique ID for testing
    test_id = datetime.now().strftime("%Y%m%d%H%M%S")
    user_id = f"test_user_{test_id}"
    room_id = f"test_room_{test_id}"
    agent_id = "test_agent"
    
    # Store various messages
    messages = [
        "Python is a popular programming language known for its readability and simplicity.",
        "JavaScript is a programming language commonly used for web development.",
        "Machine learning is a subset of AI that focuses on making computers learn from data.",
        "Data structures are ways of organizing and storing data for efficient access and modification.",
        "Algorithms are step-by-step procedures for solving problems or accomplishing tasks."
    ]
    
    print(f"Storing {len(messages)} test messages...")
    
    # Store messages
    for i, text in enumerate(messages):
        message = {
            "content": {"text": text},
            "user_id": user_id,
            "room_id": room_id,
            "agent_id": agent_id,
            "metadata": {
                "role": "assistant" if i % 2 == 0 else "user",
                "index": i
            }
        }
        await message_manager.create_memory(message)
    
    # Test queries
    queries = [
        "Tell me about programming languages",
        "What is artificial intelligence?",
        "How do I organize data efficiently?"
    ]
    
    for query in queries:
        print(f"\nSearching for: \"{query}\"")
        results = await memory_system.retrieve_similar(
            query=query,
            threshold=0.5,  # Lower threshold for demo
            limit=3,
            user_id=user_id,
            room_id=room_id,
            agent_id=agent_id
        )
        
        print(f"Found {len(results)} relevant results:")
        for i, result in enumerate(results):
            similarity = result.get("similarity", 0) * 100
            content = result.get("content", {}).get("text", "")
            print(f"  {i+1}. [{similarity:.1f}%] {content}")


async def test_rag():
    """Test RAG functionality."""
    print("\n===== Testing RAG Knowledge Management =====")
    
    # Initialize memory system
    memory_system = MemorySystem()
    rag_manager = RAGKnowledgeManager(memory_system)
    
    # Test documents
    documents = [
        {
            "title": "Introduction to Python",
            "content": """Python is a high-level, interpreted programming language known for its 
            readability and simplicity. It was created by Guido van Rossum and first released in 1991.
            Python's design philosophy emphasizes code readability with its notable use of significant 
            whitespace. It supports multiple programming paradigms, including structured, object-oriented, 
            and functional programming."""
        },
        {
            "title": "Python Data Structures",
            "content": """Python has several built-in data structures that are very useful in programming.
            Lists are mutable ordered sequences, typically used to store collections of homogeneous items.
            Tuples are immutable ordered sequences, similar to lists but cannot be changed after creation.
            Dictionaries are mutable mappings that associate keys with values, providing fast lookup.
            Sets are mutable unordered collections of unique elements, useful for membership testing."""
        }
    ]
    
    agent_id = "test_agent"
    
    print(f"Loading {len(documents)} documents into RAG knowledge base...")
    
    # Load documents
    memory_ids = await rag_manager.load_knowledge(
        documents=documents,
        chunk_size=200,  # Small for demo purposes
        chunk_overlap=50,
        agent_id=agent_id
    )
    
    print(f"Created {len(memory_ids)} memory chunks")
    
    # Test queries
    queries = [
        "What is Python programming language?",
        "Tell me about Python data structures",
        "What are dictionaries in Python?"
    ]
    
    for query in queries:
        print(f"\nGetting knowledge context for query: \"{query}\"")
        context = await rag_manager.get_knowledge_context(
            query=query,
            agent_id=agent_id,
            max_tokens=200  # Small for demo purposes
        )
        
        print(f"Context result:\n{context}")


async def main():
    """Run all tests."""
    try:
        print("=== Carrier Memory System Tests ===")
        print("Running tests with Supabase URL:", 
              os.environ.get("SUPABASE_URL", "https://localhost:8000"))
        
        await test_basic_memory()
        await test_semantic_search()
        await test_rag()
        
        print("\n=== All tests completed successfully ===")
    except Exception as e:
        print(f"Error during tests: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Initialize Supabase credentials for testing
    # You can also set these in environment variables
    os.environ.setdefault("SUPABASE_URL", "https://localhost:8000")
    os.environ.setdefault("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q")
    
    # Run the test
    asyncio.run(main())
