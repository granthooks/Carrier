#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from typing import List, Any, Tuple, Dict
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("src"))

# Import Agents SDK
from agents import Tool, function_tool
from agents.mcp import MCPServer
from agents.tool import FunctionTool

# Configure logging
logger = logging.getLogger("mcp_util_tester")
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

async def inspect_mcp_util():
    """Inspect and test the MCPUtil class implementation."""
    logger.info("Inspecting MCPUtil implementation")
    
    try:
        # Import MCPUtil
        from src.agents.mcp.util import MCPUtil
        
        # Log details about the class
        logger.info(f"MCPUtil class: {MCPUtil}")
        
        # Check for the existence of key methods
        methods_to_check = [
            "get_all_function_tools",
            "to_function_tool",
            "get_function_tools"  # This might be missing, which could be the issue
        ]
        
        for method_name in methods_to_check:
            if hasattr(MCPUtil, method_name):
                method = getattr(MCPUtil, method_name)
                logger.info(f"Found method: {method_name} - {method}")
            else:
                logger.warning(f"Method not found: {method_name}")
                
        # Check implementation of get_all_function_tools
        logger.info("Checking implementation of get_all_function_tools method")
        get_all_function_tools = getattr(MCPUtil, "get_all_function_tools", None)
        if get_all_function_tools:
            import inspect
            source = inspect.getsource(get_all_function_tools)
            logger.info(f"get_all_function_tools implementation:\n{source}")
        
        # Check for common issues in implementation
        logger.info("Checking for implementation issues")
        has_get_function_tools = hasattr(MCPUtil, "get_function_tools")
        
        if not has_get_function_tools:
            logger.error("Missing get_function_tools method - this will cause issues if get_all_function_tools tries to call it")
            logger.info("Recommended fix: Implement get_function_tools method in MCPUtil")
            
    except Exception as e:
        logger.error(f"Error inspecting MCPUtil: {e}", exc_info=True)
        
async def test_mcp_tool_conversion():
    """Test MCP tool conversion to function tool."""
    logger.info("Testing MCP tool conversion")
    
    try:
        # Create a mock MCP tool for testing
        from agents import ToolJsonSchema
        
        # Mock MCPTool class
        class MockMCPTool:
            def __init__(self, name, description, parameters):
                self.name = name
                self.description = description
                self.parameters = parameters
        
        # Create a mock MCP tool
        mock_tool = MockMCPTool(
            name="mock_search",
            description="A mock search tool",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        )
        
        # Import MCPUtil
        from src.agents.mcp.util import MCPUtil
        
        # Test to_function_tool directly
        if hasattr(MCPUtil, "to_function_tool"):
            logger.info("Testing to_function_tool method directly")
            try:
                function_tool = MCPUtil.to_function_tool(mock_tool)
                logger.info(f"Converted tool: {function_tool}")
                logger.info(f"Tool type: {type(function_tool).__name__}")
                logger.info(f"Is Tool instance: {isinstance(function_tool, Tool)}")
                
                # Check schema
                if hasattr(function_tool, "params_json_schema"):
                    logger.info(f"Function tool schema: {function_tool.params_json_schema}")
            except Exception as e:
                logger.error(f"Error converting mock tool: {e}", exc_info=True)
        else:
            logger.warning("to_function_tool method not found")
    
    except Exception as e:
        logger.error(f"Error testing MCP tool conversion: {e}", exc_info=True)

async def implement_get_function_tools():
    """Create and test an implementation of the get_function_tools method."""
    logger.info("Testing implementation of get_function_tools method")
    
    try:
        # Import MCPUtil
        from src.agents.mcp.util import MCPUtil
        
        # Check if the method already exists
        if hasattr(MCPUtil, "get_function_tools"):
            logger.info("get_function_tools method already exists")
            return
            
        # Log the suggested implementation
        suggested_impl = """
        @classmethod
        async def get_function_tools(cls, server: "MCPServer") -> list["Tool"]:
            """
            Get function tools from a single MCP server.
            
            Args:
                server: The MCP server to get tools from.
                
            Returns:
                A list of valid function tools from the MCP server.
            """
            try:
                # Import the Tool class for type checking
                from agents import Tool
                
                logger.info(f"Getting tools from MCP server: {getattr(server, 'name', 'Unnamed')}")
                
                # Get tools from the server
                mcp_tools = await server.list_tools()
                
                if not mcp_tools:
                    logger.warning(f"No tools found for MCP server: {getattr(server, 'name', 'Unnamed')}")
                    return []
                
                # Convert each tool
                function_tools = []
                for tool in mcp_tools:
                    try:
                        # Convert the MCP tool to a function tool
                        function_tool = cls.to_function_tool(tool)
                        
                        # Validate the converted tool
                        if isinstance(function_tool, Tool):
                            function_tools.append(function_tool)
                        else:
                            logger.warning(f"Converted tool is not a Tool instance: {type(function_tool)}")
                    except Exception as e:
                        # Log the error but continue with other tools
                        logger.error(f"Error converting tool {getattr(tool, 'name', 'unknown')}: {e}")
                
                logger.info(f"Converted {len(function_tools)} valid tools from MCP server: {getattr(server, 'name', 'Unnamed')}")
                return function_tools
            except Exception as e:
                logger.error(f"Error getting function tools from MCP server: {e}", exc_info=True)
                return []
        """
        
        logger.info(f"Suggested implementation for get_function_tools:\n{suggested_impl}")
        
    except Exception as e:
        logger.error(f"Error implementing get_function_tools: {e}", exc_info=True)

async def main():
    """Main test function."""
    logger.info("Starting MCP Util tests")
    
    # Inspect MCPUtil class
    await inspect_mcp_util()
    
    # Test MCP tool conversion
    await test_mcp_tool_conversion()
    
    # Implement and test get_function_tools
    await implement_get_function_tools()
    
    logger.info("MCP Util tests completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Execution interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True) 