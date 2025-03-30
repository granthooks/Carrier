#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
import contextlib
from dotenv import load_dotenv

# load .env file
load_dotenv()

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("src"))

# Import standard OpenAI Agents SDK
from agents import Agent, Tool
from agents.mcp import MCPServer, MCPServerStdio, MCPServerSse
from agents.tool import FunctionTool

# Import Carrier extensions
from src.carrier.utils.logging import configure_logging

# Configure logging
logger = logging.getLogger("mcp_tester")
logger.setLevel(logging.DEBUG)
# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Add formatter to ch
ch.setFormatter(formatter)
# Add ch to logger
logger.addHandler(ch)

# Set httpx logging level to WARNING to suppress INFO level logs
logging.getLogger("httpx").setLevel(logging.WARNING)

async def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file asynchronously."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        raise

async def load_mcp_server_configs(file_path: str = "config/mcp_servers.json") -> Dict[str, Any]:
    """Load MCP server configurations."""
    logger.info(f"Loading MCP server configurations from {file_path}")
    config_data = await load_json_file(file_path)
    return config_data.get("mcpServers", {})

async def test_mcp_server(server: MCPServer) -> Tuple[bool, List[str]]:
    """Test connection to an MCP server and list its tools."""
    server_name = getattr(server, 'name', f"Unnamed {server.__class__.__name__}")
    logger.info(f"Testing MCP server: {server_name}")
    
    tool_names = []
    success = False
    
    try:
        # Test if server is connected
        logger.info(f"Checking if server {server_name} is connected")
        if hasattr(server, 'session') and server.session:
            logger.info(f"Server {server_name} is already connected")
        else:
            logger.info(f"Server {server_name} is not connected, attempting to connect")
            await server.connect()
            logger.info(f"Connected to server {server_name}")
        
        # List tools from server
        logger.info(f"Listing tools from server {server_name}")
        tools = await server.list_tools()
        
        if not tools:
            logger.warning(f"No tools found on server {server_name}")
        else:
            logger.info(f"Found {len(tools)} tools on server {server_name}")
            
            # Log tool details
            for i, tool in enumerate(tools):
                try:
                    # Safely access tool properties
                    tool_name = getattr(tool, 'name', f"unknown_{i}")
                    tool_type = type(tool).__name__
                    tool_desc = getattr(tool, 'description', "No description")
                    logger.info(f"Tool {i+1}: {tool_name} ({tool_type}) - {tool_desc}")
                    tool_names.append(tool_name)
                    
                    # Log tool parameters for debugging
                    if hasattr(tool, 'params_json_schema'):
                        logger.debug(f"Tool {tool_name} schema: {tool.params_json_schema}")
                except Exception as e:
                    logger.error(f"Error accessing tool {i} properties: {e}")
        
        success = True
    except Exception as e:
        logger.error(f"Error testing MCP server {server_name}: {e}", exc_info=True)
    
    return success, tool_names

async def test_mcp_to_function_tool_conversion(server: MCPServer) -> None:
    """Test converting MCP tools to function tools."""
    server_name = getattr(server, 'name', f"Unnamed {server.__class__.__name__}")
    logger.info(f"Testing tool conversion for server: {server_name}")
    
    try:
        # Import MCPUtil for conversion testing
        from src.agents.mcp.util import MCPUtil
        
        # Try to convert MCP tools to function tools
        logger.info(f"Attempting to convert tools from {server_name} to function tools")
        function_tools = await MCPUtil.get_function_tools(server)
        
        if not function_tools:
            logger.warning(f"No function tools converted from server {server_name}")
        else:
            logger.info(f"Successfully converted {len(function_tools)} tools from {server_name}")
            
            # Log converted tool details
            for i, tool in enumerate(function_tools):
                if isinstance(tool, Tool):
                    logger.info(f"Converted tool {i+1}: {tool.name} ({type(tool).__name__})")
                    
                    # Additional validation
                    if isinstance(tool, FunctionTool):
                        logger.debug(f"Function tool schema: {tool.params_json_schema}")
                else:
                    logger.warning(f"Converted item {i+1} is not a Tool instance: {type(tool).__name__}")
    except Exception as e:
        logger.error(f"Error testing tool conversion for {server_name}: {e}", exc_info=True)

async def test_agent_with_mcp_servers(mcp_servers: List[MCPServer]) -> None:
    """Test initializing an agent with MCP servers and examine registered tools."""
    logger.info(f"Testing agent initialization with {len(mcp_servers)} MCP servers")
    
    try:
        # Create a simple test agent
        agent = Agent(
            name="Test Agent",
            instructions="You are a test agent.",
            mcp_servers=mcp_servers
        )
        
        # Get MCP tools
        logger.info("Fetching MCP tools through agent.get_mcp_tools()")
        mcp_tools = await agent.get_mcp_tools()
        logger.info(f"Agent.get_mcp_tools() returned {len(mcp_tools)} tools")
        
        # Log each MCP tool
        for i, tool in enumerate(mcp_tools):
            logger.info(f"MCP tool {i+1}: {tool.name} ({type(tool).__name__})")
        
        # Get all tools (MCP + built-in)
        logger.info("Fetching all tools through agent.get_all_tools()")
        all_tools = await agent.get_all_tools()
        logger.info(f"Agent.get_all_tools() returned {len(all_tools)} tools")
        
        # Check for agent.all_tool_descriptions attribute
        if hasattr(agent, 'all_tool_descriptions'):
            logger.info(f"Agent has {len(agent.all_tool_descriptions)} tool descriptions")
        else:
            logger.warning("Agent does not have all_tool_descriptions attribute")
            
    except Exception as e:
        logger.error(f"Error testing agent with MCP servers: {e}", exc_info=True)

async def main():
    """Main test function."""
    load_dotenv()
    
    mcp_server_configs = await load_mcp_server_configs()
    active_mcp_servers = []
    
    # Report all configured servers
    logger.info(f"Found {len(mcp_server_configs)} MCP server configurations")
    for server_name, config in mcp_server_configs.items():
        server_type = config.get("type")
        display_name = config.get("name", server_name)
        logger.info(f"MCP server: {server_name} ({display_name}) - Type: {server_type}")

    # Start MCP servers
    async with contextlib.AsyncExitStack() as stack:
        # Start each MCP server
        for server_name, config in mcp_server_configs.items():
            server_type = config.get("type")
            display_name = config.get("name", server_name)
            cache_tools = config.get("cache_tools_list", False)
            
            server_instance = None
            params = {}

            # Prepare environment variables
            server_env = config.get("env", {}).copy()
            for key, value in server_env.items():
                if isinstance(value, str) and value.startswith("YOUR_") and value.endswith("_HERE"):
                    env_var_name = value.replace("YOUR_", "").replace("_HERE", "")
                    env_value = os.getenv(env_var_name)
                    if env_value:
                        server_env[key] = env_value
                        logger.debug(f"Loaded env var {env_var_name} for MCP server {server_name}")
                    else:
                        logger.warning(f"Environment variable {env_var_name} not found for MCP server {server_name}")

            # Initialize appropriate server type
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
                headers = config.get("headers")
                if not url:
                    logger.error(f"Missing 'url' for sse MCP server: {server_name}")
                    continue
                server_instance = MCPServerSse(name=display_name, url=url, headers=headers, cache_tools_list=cache_tools)
            else:
                logger.error(f"Unsupported MCP server type '{server_type}' for server: {server_name}")
                continue

            if server_instance:
                logger.info(f"Starting MCP server: {server_name} ({display_name})")
                try:
                    # Use stack.enter_async_context to manage server lifecycle
                    server = await stack.enter_async_context(server_instance)
                    active_mcp_servers.append(server)
                    logger.info(f"MCP server '{server_name}' started successfully")
                except Exception as e:
                    logger.error(f"Error starting MCP server '{server_name}': {e}", exc_info=True)

        # Report MCP server status
        logger.info(f"Started {len(active_mcp_servers)} MCP servers")
        
        # Test each MCP server connection and list tools
        for server in active_mcp_servers:
            success, tool_names = await test_mcp_server(server)
            if success and tool_names:
                # Test conversion of MCP tools to function tools
                await test_mcp_to_function_tool_conversion(server)
        
        # Test agent with MCP servers
        if active_mcp_servers:
            await test_agent_with_mcp_servers(active_mcp_servers)
        else:
            logger.warning("No active MCP servers to test with agent")

    logger.info("All MCP servers shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Execution interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True) 