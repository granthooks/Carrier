#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import List, Dict, Any, Optional, Tuple, Mapping, Set
from dataclasses import dataclass, field
from dotenv import load_dotenv
import base64
from datetime import datetime
import aiohttp
import contextlib # Added for managing multiple async contexts

# load .env file
load_dotenv()

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("src"))

# Import standard OpenAI Agents SDK
from agents import Agent, Runner, RunContextWrapper, RunHooks, Usage, Tool, function_tool
from agents.mcp import MCPServer, MCPServerStdio, MCPServerSse # Added MCP imports
# from agents.function_schema import FunctionInfo # Added for tool schema handling

# Import Carrier extensions
from src.carrier.extensions.carrier_agent import AgentMemory, CarrierAgent
from src.carrier.clients.discord_client import DiscordAgentClient
from src.carrier.clients.instagram_client import InstagramAgentClient
from src.carrier.utils.logging import configure_logging
# Import tools and tool registry functionality
from src.carrier.tools import get_registered_tools

# Configure logging
logger = configure_logging()

# Set httpx logging level to WARNING to suppress INFO level logs
logging.getLogger("httpx").setLevel(logging.WARNING)

# Find the OpenAI API call in the Agent class and add before the call:
# logging.getLogger("openai").setLevel(logging.DEBUG)

# --- Configuration Loading ---

async def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file asynchronously."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # In a real async scenario, you might use aiofiles, but for config, sync is often fine.
    # Using sync here for simplicity as it's typically done at startup.
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        raise

async def load_character_file(file_path: str) -> Dict[str, Any]:
    """Load and parse the character file"""
    return await load_json_file(file_path)

async def load_mcp_server_configs(file_path: str = "config/mcp_servers.json") -> Dict[str, Any]:
    """Load MCP server configurations."""
    logger.info(f"Loading MCP server configurations from {file_path}")
    config_data = await load_json_file(file_path)
    return config_data.get("mcpServers", {})

# --- Tool Management ---

def get_available_tools(tool_config: List[str]) -> Tuple[List[Tool], Dict[str, str]]:
    """
    Get available built-in tools and their descriptions based on configuration.
    """
    return get_registered_tools(tool_config)

# --- System Prompt Building ---

def build_system_prompt(character_data: Dict[str, Any], client: str = "generic", all_tool_descriptions: Dict[str, str] = None) -> str:
    """Build a comprehensive system prompt from character data, including all tools."""
    
    system_prompt = character_data.get("system", "")
    
    # Add bio, lore, style, examples (existing logic remains the same)
    bio = character_data.get("bio", [])
    if bio:
        system_prompt += "\n\n## About You\n" + "\n".join([f"- {item}" for item in bio])
    lore = character_data.get("lore", [])
    if lore:
        system_prompt += "\n\n## Your Background\n" + "\n".join([f"- {item}" for item in lore])
    style = character_data.get("style", {})
    all_style = style.get("all", [])
    chat_style = style.get("chat", [])
    if all_style or chat_style:
        system_prompt += "\n\n## Your Communication Style\n"
        if all_style: system_prompt += "\n".join([f"- {item}" for item in all_style])
        if chat_style: system_prompt += "\n" + "\n".join([f"- {item}" for item in chat_style])
    examples = character_data.get("messageExamples", [])
    if examples and len(examples) > 0:
        system_prompt += "\n\n## Example Conversations\n"
        for i, example in enumerate(examples[:3]):
            system_prompt += f"\nExample {i+1}:\n"
            for message in example:
                role = "User" if message.get("user") != character_data.get("name") else character_data.get("name")
                content = message.get("content", {}).get("text", "")
                system_prompt += f"{role}: {content}\n"

    # Add client context (existing logic remains the same)
    system_prompt += "\n\n## Client Context\n"
    if client == "discord":
        system_prompt += "- You are interacting in a Discord server.\n"
        system_prompt += "- You'll only respond when someone mentions you by name or tags you.\n"
        system_prompt += "- Keep responses appropriately sized for a chat client.\n"
        system_prompt += "- Remember that many people might be watching this conversation.\n"
    elif client == "instagram":
        system_prompt += "- You are interacting on Instagram via direct messages.\n"
        # ... (rest of instagram context)
    else:
         system_prompt += f"- You are interacting via a {client} client.\n"

    # Updated section for ALL available tools (built-in + MCP)
    system_prompt += "\n\n## Available Tools\n"
    if not all_tool_descriptions or len(all_tool_descriptions) == 0:
        system_prompt += "- You don't have any tools available to use.\n"
    else:
        system_prompt += "You have access to the following tools:\n"
        # Sort tools alphabetically for consistency
        for tool_name in sorted(all_tool_descriptions.keys()):
            description = all_tool_descriptions[tool_name]
            # Ensure tool name is uppercase for clarity in the prompt
            system_prompt += f"- {tool_name.upper()}: {description}\n"
        system_prompt += "\nUse the LIST_AVAILABLE_TOOLS tool if you need to see this list again."

    return system_prompt

# --- Agent Initialization ---

async def initialize_agent(
    character_file: str,
    client: str = "generic",
    active_mcp_servers: Optional[List[MCPServer]] = None
) -> Tuple[CarrierAgent, AgentMemory]:
    
    """Initialize a Carrier agent from character file, including MCP tools."""
    logger.info(f"Initializing agent from {character_file} for {client}")
    
    character_data = await load_character_file(character_file)
    agent_name = character_data.get("name", "Agent")

    # 1. Get built-in tools
    tool_config = character_data.get("tools", [])
    built_in_tools, built_in_tool_descriptions = get_available_tools(tool_config)
    
    # 2. Get MCP tools
    mcp_tool_descriptions: Dict[str, str] = {}
    if active_mcp_servers:
        logger.info(f"Fetching tools from {len(active_mcp_servers)} active MCP server(s) for {agent_name}")
        for server in active_mcp_servers:
            server_name_log = getattr(server, 'name', f"Unnamed {server.__class__.__name__}")
            try:
                logger.debug(f"Fetching tools from MCP server: {server_name_log}")
                
                # The SDK's list_tools returns a list of MCPTool objects
                try:
                    tools_list = await server.list_tools()
                    if not tools_list:
                        logger.debug(f"No tools found for MCP server: {server_name_log}")
                        continue
                        
                    # Add server reference to each tool
                    for tool in tools_list:
                        # Attach the server reference to each tool
                        tool.server = server
                        
                    # Extract tool information for display purposes
                    for tool in tools_list:
                        try:
                            # Access tool properties safely with getattr for resilience
                            tool_name = getattr(tool, 'name', None)
                            if not tool_name:
                                logger.warning(f"Found tool without name from {server_name_log}, skipping")
                                continue
                                
                            description = getattr(tool, 'description', "No description provided.")
                            
                            # Store the tool information for system prompt
                            mcp_tool_descriptions[tool_name.upper()] = description
                            logger.debug(f"Found MCP tool '{tool_name}' from server '{server_name_log}'")
                        except Exception as tool_e:
                            logger.error(f"Error processing tool from {server_name_log}: {tool_e}")
                except Exception as list_e:
                    logger.error(f"Error listing tools from MCP server {server_name_log}: {list_e}")
            except Exception as e:
                logger.error(f"Failed to interact with MCP server '{server_name_log}': {e}", exc_info=True)

    # 3. Combine tools and descriptions
    # The Agent constructor expects Tool objects for built-in, schemas (dicts) for MCP are handled internally via mcp_servers param
    all_tools_for_prompt = {**built_in_tool_descriptions, **mcp_tool_descriptions}
    
    # 4. Build system prompt with all tools
    system_prompt = build_system_prompt(character_data, client, all_tools_for_prompt)
    
    # 5. Initialize the standard OpenAI Agent, passing MCP servers
    # Note: The 'tools' parameter here should only contain the *built-in* Tool objects.
    # The SDK handles MCP tool availability via the 'mcp_servers' parameter.
    
    # Make sure all tools are valid Tool objects from the agents package
    validated_tools = []
    
    for i, tool in enumerate(built_in_tools):
        if isinstance(tool, Tool):
            validated_tools.append(tool)
            logger.debug(f"Valid built-in tool {i}: {tool.name} - Type: {type(tool).__name__}")
        else:
            logger.warning(f"Skipping invalid tool {getattr(tool, 'name', f'unknown_{i}')} - Type: {type(tool).__name__}")
    
    # Validate MCP servers
    validated_mcp_servers = []
    for server in (active_mcp_servers or []):
        if hasattr(server, 'list_tools') and callable(server.list_tools):
            validated_mcp_servers.append(server)
            logger.debug(f"Valid MCP server: {getattr(server, 'name', 'Unnamed')}")
        else:
            logger.warning(f"Skipping invalid MCP server: {getattr(server, 'name', f'Unnamed')} - Missing required methods")
    
    # Log summary of available tools
    logger.info(f"Initializing agent with {len(validated_tools)} built-in tools and {len(validated_mcp_servers)} MCP servers")
    
    # Create the base agent with validated components
    base_agent = Agent(
        name=agent_name,
        instructions=system_prompt,
        model=character_data.get("model", "gpt-4o"),
        tools=validated_tools,
        mcp_servers=validated_mcp_servers
    )
    
    # 6. Initialize memory
    memory = AgentMemory(client=client)
    
    # 7. Convert to CarrierAgent and store combined tool info
    agent = CarrierAgent.from_agent(base_agent, memory)
    agent.all_tool_descriptions = all_tools_for_prompt # Store for potential use by LIST_AVAILABLE_TOOLS

    # Log combined tools
    tools_log_list = sorted(all_tools_for_prompt.keys())
    logger.info(f"{agent.name} initialized for {client} with tools: {', '.join(tools_log_list) if tools_log_list else 'NO TOOLS'}")
    
    # Add this to initialize_agent function before creating the base agent
    for server in validated_mcp_servers:
        # Test if the server can list tools
        try:
            tools = await server.list_tools()
            logger.info(f"MCP server {getattr(server, 'name', 'Unknown')} has {len(tools)} tools")
        except Exception as e:
            logger.error(f"Error listing tools from MCP server {getattr(server, 'name', 'Unknown')}: {e}")

    # Then after creating the base agent
    # Test if MCP tools can be retrieved from the agent
    # try:
    #     mcp_tools = await base_agent.get_mcp_tools()
    #     for tool in mcp_tools:
    #         if hasattr(tool, "params_json_schema"):
    #             schema = tool.params_json_schema
    #             # logger.info(f"Tool {tool.name} schema: {json.dumps(schema, indent=2)}")
    # except Exception as e:
    #     logger.error(f"Error getting MCP tools: {e}")

    return agent, memory

# --- Main Execution Logic ---

async def main():
    """Main function to run agent clients based on character configuration"""
    load_dotenv()
    
    character_files = [
        "characters/assistantbot.json",
        # Add other character files here
    ]
    
    mcp_server_configs = await load_mcp_server_configs()
    required_mcp_server_names: Set[str] = set()
    agent_configs = {}

    # First pass: Load all character configs and identify unique required MCP servers
    logger.info("Identifying required MCP servers across all agents...")
    for char_file in character_files:
        try:
            character_data = await load_character_file(char_file)
            agent_configs[char_file] = character_data # Store config for later use
            mcp_names = character_data.get("mcp_servers", [])
            required_mcp_server_names.update(mcp_names)
            logger.debug(f"Agent {character_data.get('name')} requires MCP servers: {mcp_names}")
        except Exception as e:
            logger.error(f"Error loading character file {char_file}: {e}")
            
    logger.info(f"Unique MCP servers required: {required_mcp_server_names or 'None'}")

    client_tasks = []
    active_mcp_servers_map: Dict[str, MCPServer] = {}

    # Use AsyncExitStack to manage MCP server lifecycles
    async with contextlib.AsyncExitStack() as stack:
        # Start all required MCP servers concurrently
        startup_tasks = []
        for server_name in required_mcp_server_names:
            if server_name in mcp_server_configs:
                config = mcp_server_configs[server_name]
                server_type = config.get("type")
                display_name = config.get("name", server_name) # Use provided name or key
                cache_tools = config.get("cache_tools_list", False)
                
                server_instance = None
                params = {}

                # Prepare environment variables, loading from os.getenv if placeholder exists
                server_env = config.get("env", {}).copy()
                for key, value in server_env.items():
                    if isinstance(value, str) and value.startswith("YOUR_") and value.endswith("_HERE"):
                         # Attempt to load from environment variables
                         env_var_name = value.replace("YOUR_", "").replace("_HERE", "")
                         env_value = os.getenv(env_var_name)
                         if env_value:
                              server_env[key] = env_value
                              logger.debug(f"Loaded env var {env_var_name} for MCP server {server_name}")
                         else:
                              logger.warning(f"Environment variable {env_var_name} not found for MCP server {server_name}. Placeholder '{value}' will be used.")
                              # Keep the placeholder or handle as error depending on requirements
                              # For now, keep placeholder to avoid crashing if key is optional for server
                              # server_env[key] = "" # Or raise error

                # For filesystem server, add additional checks
                if server_name == "filesystem" or "filesystem" in server_name:
                    workspace_path = os.path.abspath("mcp_workspace")
                    logger.info(f"Filesystem MCP server workspace path: {workspace_path}")
                    logger.info(f"Path exists: {os.path.exists(workspace_path)}")
                    logger.info(f"Path is writable: {os.access(workspace_path, os.W_OK)}")
                    
                    # Check environment variables
                    config_env = config.get("env", {})
                    logger.info(f"Filesystem MCP server environment: {config_env}")
                    
                    # Log the full resolved command
                    cmd = config.get("command", "")
                    args = config.get("args", [])
                    logger.info(f"Filesystem MCP command: {cmd} {' '.join(args)}")

                if server_type == "stdio":
                    params = {
                        "command": config.get("command"),
                        "args": config.get("args", []),
                        "cwd": config.get("cwd"),
                        "env": server_env,
                    }
                    if not params["command"]:
                         logger.error(f"Missing 'command' for stdio MCP server: {server_name}")
                         continue
                    server_instance = MCPServerStdio(name=display_name, params=params, cache_tools_list=cache_tools)
                elif server_type == "sse":
                    url = config.get("url")
                    headers = config.get("headers") # Headers might contain auth tokens
                    if not url:
                         logger.error(f"Missing 'url' for sse MCP server: {server_name}")
                         continue
                    # Note: MCPServerSse doesn't explicitly take env, but headers can be used for tokens
                    server_instance = MCPServerSse(name=display_name, url=url, headers=headers, cache_tools_list=cache_tools)
                else:
                    logger.error(f"Unsupported MCP server type '{server_type}' for server: {server_name}")
                    continue

                if server_instance:
                    logger.info(f"Attempting to start MCP server: {server_name} ({display_name})")
                    # Use stack.enter_async_context to manage the server's lifecycle
                    startup_tasks.append( (server_name, stack.enter_async_context(server_instance)) )

            else:
                logger.warning(f"Configuration not found for required MCP server: {server_name}")

        # Wait for all servers to start (or fail)
        try:
            started_servers = await asyncio.gather(*(task for _, task in startup_tasks))
            # Populate the map of active servers
            for i, (server_name, _) in enumerate(startup_tasks):
                 active_mcp_servers_map[server_name] = started_servers[i]
                 logger.info(f"MCP server '{server_name}' started successfully.")
        except Exception as e:
            logger.error(f"Error starting one or more MCP servers: {e}", exc_info=True)
            # Depending on requirements, might want to exit or continue without failed servers

        logger.info(f"Active MCP servers: {list(active_mcp_servers_map.keys())}")
        logger.info("-------------------- Finished loading MCP servers --------------------")

        # Inside the main function, before starting MCP servers
        for server_name in required_mcp_server_names:
            if server_name in mcp_server_configs:
                config = mcp_server_configs[server_name]
                if "filesystem" in server_name.lower():
                    logger.info(f"Filesystem MCP server configuration:")
                    logger.info(f"  Command: {config.get('command')}")
                    logger.info(f"  Args: {config.get('args')}")
                    logger.info(f"  CWD: {config.get('cwd', 'Not specified')}")
                    logger.info(f"  Environment variables: {config.get('env', {})}")
                    
                    # Check if ALLOWED_PATHS is properly set
                    env_vars = config.get('env', {})
                    allowed_paths = env_vars.get('ALLOWED_PATHS', 'Not specified')
                    logger.info(f"  ALLOWED_PATHS: {allowed_paths}")
                    
                    # Make sure the directory exists
                    if allowed_paths != 'Not specified':
                        # Convert to normalized path
                        normalized_path = os.path.normpath(allowed_paths)
                        logger.info(f"  Normalized allowed path: {normalized_path}")
                        logger.info(f"  Path exists: {os.path.exists(normalized_path)}")
                        logger.info(f"  Path is directory: {os.path.isdir(normalized_path)}")
                        logger.info(f"  Path is writable: {os.access(normalized_path, os.W_OK)}")
                        
                        # Create the directory if it doesn't exist
                        if not os.path.exists(normalized_path):
                            try:
                                os.makedirs(normalized_path, exist_ok=True)
                                logger.info(f"  Created directory: {normalized_path}")
                            except Exception as e:
                                logger.error(f"  Failed to create directory: {e}")

        # Second pass: Initialize agents and clients using the active servers
        logger.info("Initializing agents and clients...")
        for char_file, character_data in agent_configs.items():
            try:
                username = character_data.get("username")
                supported_clients = character_data.get("clients", [])
                required_servers_for_agent = character_data.get("mcp_servers", [])
                
                # Get the active server instances needed by this agent
                agent_mcp_instances = [active_mcp_servers_map[name] for name in required_servers_for_agent if name in active_mcp_servers_map]
                if len(agent_mcp_instances) != len(required_servers_for_agent):
                     missing = set(required_servers_for_agent) - set(active_mcp_servers_map.keys())
                     logger.warning(f"Agent {character_data.get('name')} requires MCP servers that failed to start or are not configured: {missing}")

                # Initialize clients for this agent
                if "Discord" in supported_clients:
                    discord_token = os.getenv(f"{username}_DISCORD_API_TOKEN")
                    if discord_token:
                        agent, memory = await initialize_agent(char_file, client="discord", active_mcp_servers=agent_mcp_instances)
                        discord_client = DiscordAgentClient(agent, memory)
                        discord_config = character_data.get("discord_config", {})
                        discord_client.initial_channel = discord_config.get("initial_channel")
                        discord_client.initial_message = discord_config.get("initial_message")
                        client_tasks.append(asyncio.create_task(discord_client.start(discord_token)))
                    else:
                        logger.error(f"Missing Discord token for {username}")
                
                if "Instagram" in supported_clients:
                    instagram_token = os.getenv(f"{username}_INSTAGRAM_ACCESS_TOKEN")
                    if instagram_token:
                        agent, memory = await initialize_agent(char_file, client="instagram", active_mcp_servers=agent_mcp_instances)
                        instagram_client = InstagramAgentClient(agent, memory)
                        client_tasks.append(asyncio.create_task(instagram_client.run(instagram_token)))
                    else:
                        logger.error(f"Missing Instagram token for {username}")
                        
                # Add other client initializations here...

            except Exception as e:
                logger.error(f"Error initializing agent or client from {char_file}: {e}", exc_info=True)

        # Keep the main task running while client tasks are active
        if client_tasks:
            logger.info("-------------------------------- Agents Starting --------------------------------")
            logger.info(f"Running {len(client_tasks)} client task(s)...")
            await asyncio.gather(*client_tasks)
        else:
            logger.error("No clients were successfully initialized to run.")

    logger.info("All MCP servers shut down.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Execution interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
