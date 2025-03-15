#!/usr/bin/env python3
import asyncio
import json
import os
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("src"))

from agents import Agent, Runner, RunContextWrapper, RunHooks, Usage, Tool, TResponseInputItem


@dataclass
class AgentMemory:
    """Maintains the agent's memory between interactions"""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_info: Dict[str, Any] = field(default_factory=dict)
    last_topics: List[str] = field(default_factory=list)


class TifaHooks(RunHooks):
    """Implements hooks for the runtime loop stages"""
    
    def __init__(self):
        self.processed_messages = 0
    
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Step 3: Message Processing pipeline begins"""
        print(f"[SYSTEM] Processing message...")
        self.processed_messages += 1
    
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        """Step 5: Action Execution begins"""
        print(f"[SYSTEM] Executing tool: {tool.name}")
    
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        """Step 5: Action Execution completes"""
        print(f"[SYSTEM] Tool completed")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Step 6: Evaluation and Step 7: Memory Storage complete"""
        memory: AgentMemory = context.context
        
        # Store conversation in memory for future context
        if hasattr(output, 'content') and output.content:
            memory.conversation_history.append({
                "role": "assistant",
                "content": output.content,
                "timestamp": "now"  # In a real implementation, use actual timestamp
            })
            print(f"Memory contains {len(memory.conversation_history)} messages")
        
        print(f"[SYSTEM] Response generated and stored in memory")

    # print nicely formatted memory
    def format_memory(memory: AgentMemory) -> str:
       result = "=== AGENT MEMORY STATE ===\n"
       result += f"User Info: {json.dumps(memory.user_info, indent=2)}\n"
       result += f"Active Topics: {', '.join(memory.last_topics)}\n"
       result += "Recent Conversation:\n"
       for msg in memory.conversation_history[-5:]:  # Show last 5 messages
           role = msg.get('role', 'unknown')
           content = msg.get('content', '')[:50] + '...' if len(msg.get('content', '')) > 50 else msg.get('content', '')
           result += f"  [{role}]: {content}\n"
       return result

async def load_character_file(file_path: str) -> Dict[str, Any]:
    """Load and parse the character file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Character file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_system_prompt(character_data: Dict[str, Any]) -> str:
    """Build a comprehensive system prompt from character data"""
    
    # Start with the basic system prompt
    system_prompt = character_data.get("system", "")
    
    # Add bio information
    bio = character_data.get("bio", [])
    if bio:
        system_prompt += "\n\n## About You\n" + "\n".join([f"- {item}" for item in bio])
    
    # Add background/lore
    lore = character_data.get("lore", [])
    if lore:
        system_prompt += "\n\n## Your Background\n" + "\n".join([f"- {item}" for item in lore])
    
    # Add communication style
    style = character_data.get("style", {})
    all_style = style.get("all", [])
    chat_style = style.get("chat", [])
    
    if all_style or chat_style:
        system_prompt += "\n\n## Your Communication Style\n"
        if all_style:
            system_prompt += "\n".join([f"- {item}" for item in all_style])
        if chat_style:
            system_prompt += "\n" + "\n".join([f"- {item}" for item in chat_style])
    
    # Add conversation examples if available
    examples = character_data.get("messageExamples", [])
    if examples and len(examples) > 0:
        system_prompt += "\n\n## Example Conversations\n"
        for i, example in enumerate(examples[:3]):  # Limit to 3 examples
            system_prompt += f"\nExample {i+1}:\n"
            for message in example:
                role = "User" if message.get("user") != character_data.get("name") else character_data.get("name")
                content = message.get("content", {}).get("text", "")
                system_prompt += f"{role}: {content}\n"
    
    return system_prompt


async def initialize_agent(character_file: str) -> Agent:
    """Step 1: Agent Initialization"""
    print(f"[SYSTEM] Initializing agent from {character_file}")
    
    # Load the character file
    character_data = await load_character_file(character_file)
    
    # Build the system prompt from character data
    system_prompt = build_system_prompt(character_data)
    
    # Initialize the agent
    agent = Agent(
        name=character_data.get("name", "Tifa"),
        instructions=system_prompt,
        # No tools for now, as specified in the task
    )
    
    print(f"[SYSTEM] Agent {agent.name} initialized")
    return agent


async def main():
    """Main runtime loop implementation"""
    # Step 1: Agent Initialization
    agent = await initialize_agent("characters/tifa.json")
    
    # Initialize memory for context
    memory = AgentMemory()
    
    # Initialize hooks for the runtime stages
    hooks = TifaHooks()
    
    # Initialize conversation history for the agent
    input_items: List[TResponseInputItem] = []
    
    print(f"\n{'=' * 50}")
    print(f"Welcome to a chat with {agent.name}!")
    print(f"Type 'exit', 'quit', or 'bye' to end the conversation.")
    print(f"{'=' * 50}\n")
    
    while True:
        # Step 2: Message Reception
        user_input = input("You: ")   # ... wait for user input
        
        # Check if user wants to exit
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print(f"\n{agent.name}: Goodbye! It was nice chatting with you.")
            break
        
        # Store user message in memory
        memory.conversation_history.append({
            "role": "user",
            "content": user_input,
            "timestamp": "now"  # In a real implementation, use actual timestamp
        })
        
        # Add user input to input items
        input_items.append({"content": user_input, "role": "user"})
        
        # Get response from the Agent
        result = await Runner.run(
            agent, 
            input_items, 
            context=memory,
            hooks=hooks
        )
        
        # Get the final message from the agent
        agent_response = result.final_output
        
        # Display the response
        print(f"{agent.name}: {agent_response}")
        
        # Update input items with the full conversation history for context
        input_items = result.to_input_list()


if __name__ == "__main__":
    asyncio.run(main())
