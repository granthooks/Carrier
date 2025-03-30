import asyncio
import json
import logging
import os
from src.agents.mcp.util import MCPUtil

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to load variables from .env file
def load_env_from_dotenv():
    """Load environment variables from .env file."""
    try:
        # Try to use python-dotenv if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            logger.info("Loaded environment variables from .env using python-dotenv")
        except ImportError:
            # Fallback to manual .env parsing if dotenv isn't installed
            logger.info("python-dotenv not installed, using manual .env parsing")
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"\'')
                logger.info("Loaded environment variables from .env manually")
            else:
                logger.warning(".env file not found")
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")

async def test_brave_search(server):
    """Test the brave_web_search tool directly."""
    try:
        # Manually create a valid tool call
        tool_name = "brave_web_search"
        tool_args = {"query": "test query about Python programming"}
        
        logger.info(f"Testing direct call to {tool_name} with args: {tool_args}")
        
        # Get the tool object from the server
        tools = await server.list_tools()
        logger.info(f"Available tools: {[t.name for t in tools]}")
        
        tool = next((t for t in tools if t.name == tool_name), None)
        
        if not tool:
            logger.error(f"Tool {tool_name} not found on server")
            return
        
        logger.info(f"Found tool: {tool.name} - Description: {getattr(tool, 'description', 'No description')}")
        logger.info(f"Tool schema: {json.dumps(getattr(tool, 'inputSchema', {}), indent=2)}")
        
        # Call the tool directly
        logger.info(f"Calling server.call_tool directly with args: {tool_args}")
        result = await server.call_tool(tool_name, tool_args)
        logger.info(f"Direct tool call result: {result}")
        
        # pause before next test so rate limit is not hit
        logger.info("Pausing before next test...")
        await asyncio.sleep(5)
        
        # Also test via MCPUtil for comparison
        # First add server reference to the tool
        tool.server = server
        
        # Then use MCPUtil to invoke
        context_mock = type('ContextMock', (), {})()  # Simple mock object
        input_json = json.dumps(tool_args)
        logger.info(f"Calling MCPUtil.invoke_mcp_tool with input_json: {input_json}")
        result2 = await MCPUtil.invoke_mcp_tool(server, tool, context_mock, input_json)
        logger.info(f"MCPUtil invocation result: {result2}")
        
    except Exception as e:
        logger.error(f"Error testing brave_web_search: {e}", exc_info=True)

async def main():
    # Load environment variables from .env file
    load_env_from_dotenv()
    
    # Import the correct classes for MCP server creation
    from src.agents.mcp.server import MCPServerStdio, MCPServerStdioParams
    
    # Get Brave API Key from environment variables (now loaded from .env)
    brave_api_key = os.environ.get("BRAVE_API_KEY")
    
    # Check if API key exists
    if not brave_api_key:
        logger.error("BRAVE_API_KEY not found in .env or environment variables")
        logger.error("Please add BRAVE_API_KEY=your_api_key_here to your .env file")
        return
    
    # First create the params object using the new configuration
    server_params = MCPServerStdioParams(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={"BRAVE_API_KEY": brave_api_key}
    )
    
    # Then create the server with the params
    server = MCPServerStdio(
        params=server_params,
        cache_tools_list=True,
        name="brave-search"
    )
    
    # Connect to the server
    logger.info("Connecting to Brave search server...")
    await server.connect()
    
    try:
        logger.info("Connected to server. Testing brave_web_search...")
        await test_brave_search(server)
    finally:
        logger.info("Cleaning up server...")
        await server.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 