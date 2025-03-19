#!/usr/bin/env python
"""Command-line interface for managing the Carrier memory system."""

"""
# List memories
python -m src.tools.memory_cli list --agent assistant --format

# Clear memories
python -m src.tools.memory_cli clear assistant

"""
import argparse
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

# Add parent directory to path to enable imports
sys.path.append(str(Path(__file__).parent.parent))

from agents.memory import MemorySystem, MessageManager


async def list_memories(
    supabase_url: str,
    supabase_key: str,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    room_id: Optional[str] = None,
    limit: int = 20,
    schema_name: str = "carrier_memory",
    format_output: bool = False
) -> None:
    """List memories based on filters.
    
    Args:
        supabase_url: Supabase URL
        supabase_key: Supabase API key
        agent_id: Filter by agent ID
        user_id: Filter by user ID
        memory_type: Filter by memory type
        room_id: Filter by room ID
        limit: Maximum number of memories to retrieve
        schema_name: Schema name
        format_output: Whether to format the output for readability
    """
    memory_system = MemorySystem(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        schema_name=schema_name
    )
    
    memories = await memory_system.get_memories(
        memory_type=memory_type,
        user_id=user_id,
        room_id=room_id,
        agent_id=agent_id,
        limit=limit,
        order_by="created_at",
        ascending=False  # Most recent first
    )
    
    if not memories:
        print("No memories found with the specified criteria.")
        return
    
    if format_output:
        for memory in memories:
            print(f"ID: {memory.get('id')}")
            print(f"Type: {memory.get('type')}")
            print(f"Agent: {memory.get('agent_id')}")
            print(f"User: {memory.get('user_id')}")
            print(f"Room: {memory.get('room_id')}")
            
            # Format content based on type
            content = memory.get('content', {})
            if isinstance(content, dict) and 'text' in content:
                print(f"Content: {content['text'][:100]}...")
            else:
                print(f"Content: {str(content)[:100]}...")
                
            print(f"Created: {memory.get('created_at')}")
            print("-" * 40)
    else:
        # JSON output for scripting
        for memory in memories:
            # Remove embedding for cleaner output
            if 'embedding' in memory:
                del memory['embedding']
            print(json.dumps(memory))


async def clear_memories(
    supabase_url: str,
    supabase_key: str,
    agent_id: str,
    user_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    room_id: Optional[str] = None,
    older_than: Optional[int] = None,
    schema_name: str = "carrier_memory",
    confirm: bool = False
) -> None:
    """Clear memories for an agent.
    
    Args:
        supabase_url: Supabase URL
        supabase_key: Supabase API key
        agent_id: Agent ID to clear memories for
        user_id: Filter by user ID
        memory_type: Filter by memory type
        room_id: Filter by room ID
        older_than: Delete memories older than this many days
        schema_name: Schema name
        confirm: Skip confirmation prompt
    """
    if not agent_id:
        print("Error: agent_id is required")
        return
        
    memory_system = MemorySystem(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        schema_name=schema_name
    )
    
    # Convert older_than to ISO format if provided
    older_than_iso = None
    if older_than:
        older_than_date = datetime.now() - timedelta(days=older_than)
        older_than_iso = older_than_date.isoformat()
    
    if not confirm:
        print(f"This will delete all memories for agent '{agent_id}'.")
        if user_id:
            print(f"Filtered to user '{user_id}'.")
        if room_id:
            print(f"Filtered to room '{room_id}'.")
        if memory_type:
            print(f"Filtered to type '{memory_type}'.")
        if older_than:
            print(f"Filtered to memories older than {older_than} days.")
            
        response = input("Are you sure? (y/N): ")
        if response.lower() != 'y':
            print("Operation cancelled.")
            return
    
    deleted_count = await memory_system.delete_memories(
        agent_id=agent_id,
        user_id=user_id,
        memory_type=memory_type,
        room_id=room_id,
        older_than=older_than_iso
    )
    
    print(f"Deleted {deleted_count} memories.")


async def test_similar(
    supabase_url: str,
    supabase_key: str,
    query: str,
    agent_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    threshold: float = 0.7,
    limit: int = 5,
    schema_name: str = "carrier_memory"
) -> None:
    """Test similar memory retrieval.
    
    Args:
        supabase_url: Supabase URL
        supabase_key: Supabase API key
        query: Query text
        agent_id: Filter by agent ID
        memory_type: Filter by memory type
        threshold: Similarity threshold
        limit: Maximum number of results
        schema_name: Schema name
    """
    memory_system = MemorySystem(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        schema_name=schema_name
    )
    
    results = await memory_system.retrieve_similar(
        query=query,
        threshold=threshold,
        limit=limit,
        memory_type=memory_type,
        agent_id=agent_id
    )
    
    if not results:
        print("No similar memories found.")
        return
    
    print(f"Found {len(results)} similar memories:")
    for i, result in enumerate(results):
        similarity = result.get('similarity', 0) * 100
        print(f"\n--- Result {i+1} (Similarity: {similarity:.1f}%) ---")
        print(f"ID: {result.get('id')}")
        print(f"Type: {result.get('type')}")
        print(f"Agent: {result.get('agent_id')}")
        
        # Format content based on type
        content = result.get('content', {})
        if isinstance(content, dict) and 'text' in content:
            print(f"Content: {content['text']}")
        else:
            print(f"Content: {json.dumps(content)}")


async def initialize_db(
    supabase_url: str,
    supabase_key: str,
    schema_name: str = "carrier_memory"
) -> None:
    """Initialize the memory database schema.
    
    Args:
        supabase_url: Supabase URL
        supabase_key: Supabase API key
        schema_name: Schema name to create
    """
    memory_system = MemorySystem(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        schema_name=schema_name
    )
    
    print(f"Initializing memory schema '{schema_name}'...")
    try:
        await memory_system._ensure_schema()
        print("Schema initialization complete.")
    except Exception as e:
        print(f"Error ensuring memory schema: {str(e)}")
        
        # Provide helpful troubleshooting information
        if "SSL" in str(e) or "wrong version number" in str(e):
            print("\nTroubleshooting suggestions:")
            print("1. For local Supabase, use 'http://' instead of 'https://'")
            print("2. Check if the URL is correct (current URL: {})".format(supabase_url))
            print("3. Verify that Supabase is running at the specified URL")
            print("\nTry running with the corrected URL, e.g.:")
            if supabase_url.startswith("https://localhost"):
                suggested_url = supabase_url.replace("https://", "http://")
                print(f"python -m src.tools.memory_cli init --url {suggested_url}")


def main():
    parser = argparse.ArgumentParser(description="Carrier Memory System CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--url", help="Supabase URL", default="http://localhost:8000")
    parent_parser.add_argument("--key", help="Supabase API key", 
                              default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE")
    parent_parser.add_argument("--schema", help="Schema name", default="carrier_memory")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List memories", parents=[parent_parser])
    list_parser.add_argument("--agent", help="Filter by agent ID")
    list_parser.add_argument("--user", help="Filter by user ID")
    list_parser.add_argument("--type", help="Filter by memory type")
    list_parser.add_argument("--room", help="Filter by room ID")
    list_parser.add_argument("--limit", type=int, default=20, help="Limit results")
    list_parser.add_argument("--format", action="store_true", help="Format output for readability")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear memories", parents=[parent_parser])
    clear_parser.add_argument("agent", help="Agent ID to clear memories for")
    clear_parser.add_argument("--user", help="Filter by user ID")
    clear_parser.add_argument("--type", help="Filter by memory type")
    clear_parser.add_argument("--room", help="Filter by room ID")
    clear_parser.add_argument("--older-than", type=int, help="Delete memories older than days")
    clear_parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    
    # Similar command
    similar_parser = subparsers.add_parser("similar", help="Test similar memory retrieval", parents=[parent_parser])
    similar_parser.add_argument("query", help="Query text")
    similar_parser.add_argument("--agent", help="Filter by agent ID")
    similar_parser.add_argument("--type", help="Filter by memory type")
    similar_parser.add_argument("--threshold", type=float, default=0.7, help="Similarity threshold")
    similar_parser.add_argument("--limit", type=int, default=5, help="Maximum results")
    
    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize database schema", parents=[parent_parser])
    
    args = parser.parse_args()
    
    if args.command == "list":
        asyncio.run(list_memories(
            supabase_url=args.url,
            supabase_key=args.key,
            agent_id=args.agent,
            user_id=args.user,
            memory_type=args.type,
            room_id=args.room,
            limit=args.limit,
            schema_name=args.schema,
            format_output=args.format
        ))
    elif args.command == "clear":
        asyncio.run(clear_memories(
            supabase_url=args.url,
            supabase_key=args.key,
            agent_id=args.agent,
            user_id=args.user,
            memory_type=args.type,
            room_id=args.room,
            older_than=args.older_than,
            schema_name=args.schema,
            confirm=args.yes
        ))
    elif args.command == "similar":
        asyncio.run(test_similar(
            supabase_url=args.url,
            supabase_key=args.key,
            query=args.query,
            agent_id=args.agent,
            memory_type=args.type,
            threshold=args.threshold,
            limit=args.limit,
            schema_name=args.schema
        ))
    elif args.command == "init":
        asyncio.run(initialize_db(
            supabase_url=args.url,
            supabase_key=args.key,
            schema_name=args.schema
        ))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
