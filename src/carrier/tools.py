from typing import Optional, Dict, List, Tuple, Any
from agents import Tool, function_tool
from src.agents.run_context import RunContextWrapper
import aiohttp
import base64
import logging
import inspect

# Configure logging
logger = logging.getLogger(__name__)

# Import the CarrierAgent at the module level but AFTER other imports
# to avoid circular imports during initial loading
from src.carrier.extensions.carrier_agent import CarrierAgent

# --- Tool Definitions ---

@function_tool()
async def GET_WEATHER(location: str) -> str:
    """
    Get the current weather for a location.

    Args:
        location: The location to get weather for (not actually used in this implementation)

    Returns:
        A string describing the weather
    """
    # This is a simple implementation that always returns "sunny"
    # Handle default case inside the function instead of in the parameter
    if not location or location.lower() == "default":
        location = "default location"

    logger.info(f"Weather tool called for location: {location}")
    return "sunny"

@function_tool()
async def generate_image(description: str) -> Optional[bytes]:
    """
    Generate an image using the local image generation API

    Args:
        description: A detailed description of the image to generate

    Returns:
        Bytes of the generated image, or None if generation failed
    """
    try:
        # Use aiohttp to make an async HTTP request
        async with aiohttp.ClientSession() as session:
            payload = {"image_description": description}
            headers = {"Content-Type": "application/json"}

            # Make the request to the local image generation API
            async with session.post(
                "https://localhost:9080",
                json=payload,
                headers=headers,
                ssl=False  # Disable SSL verification for local development
            ) as response:
                if response.status != 200:
                    logger.error(f"Image generation API returned status {response.status}")
                    return None

                # Parse the response JSON to get the base64 image data
                response_data = await response.json()
                if not response_data or "base64_image" not in response_data:
                    logger.error("No base64 image data in response")
                    return None

                # Decode the base64 string to bytes
                image_bytes = base64.b64decode(response_data["base64_image"])
                return image_bytes

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

class ToolExecutionWrapper:
    """Wrapper class for tool execution with context."""
    
    @staticmethod
    @function_tool(name_override="LIST_AVAILABLE_TOOLS", description_override="Lists all tools available to the agent")
    async def list_available_tools() -> str:
        """
        Lists all the tools currently available to the agent, including built-in and MCP tools.
        Use this tool if you need a reminder of the tools you can use.

        Returns:
            A formatted string listing the available tools and their descriptions.
        """
        logger.info("LIST_AVAILABLE_TOOLS called")
        
        try:
            # Access the current context without using a function parameter
            from agents.run_context import get_current_context
            
            # Get the agent from the context
            agent = get_current_context()
            
            if not agent or not hasattr(agent, 'all_tool_descriptions') or not agent.all_tool_descriptions:
                logger.warning("Agent has no tool descriptions")
                return "You currently have no tools available."
            
            tool_descriptions = agent.all_tool_descriptions
            
            # Build the response
            response_lines = ["Here are the tools available to you:"]
            # Sort tools alphabetically for consistent output
            for tool_name in sorted(tool_descriptions.keys()):
                description = tool_descriptions[tool_name]
                response_lines.append(f"- {tool_name.upper()}: {description}")
            
            return "\n".join(response_lines)
        except Exception as e:
            logger.error(f"Error in LIST_AVAILABLE_TOOLS: {e}")
            return f"Error retrieving available tools: {str(e)}"

# Update TOOL_REGISTRY to use the new implementation
TOOL_REGISTRY: Dict[str, Tool] = {
    "GET_WEATHER": GET_WEATHER,
    "GENERATE_IMAGE": generate_image,
    "LIST_AVAILABLE_TOOLS": ToolExecutionWrapper.list_available_tools,
}

def get_registered_tools(tool_config: List[str]) -> Tuple[List[Tool], Dict[str, str]]:
    """
    Get tools and their descriptions based on requested tool names.
    
    Args:
        tool_config: List of tool names to retrieve
        
    Returns:
        Tuple of (list of Tool objects, dict of tool descriptions)
    """
    configured_tools: List[Tool] = []
    tool_descriptions: Dict[str, str] = {}
    
    # Always include LIST_AVAILABLE_TOOLS by default
    if "LIST_AVAILABLE_TOOLS" not in tool_config:
        tool_config.append("LIST_AVAILABLE_TOOLS")
    
    for tool_name in tool_config:
        tool_name_upper = tool_name.upper()  # Normalize name
        if tool_name_upper in TOOL_REGISTRY:
            tool = TOOL_REGISTRY[tool_name_upper]
            # Verify that this is a valid Tool object before adding
            if isinstance(tool, Tool):
                configured_tools.append(tool)
                
                # Extract description from docstring or tool metadata
                description = "No description available"
                if hasattr(tool, 'description') and tool.description:
                    description = tool.description
                elif hasattr(tool, 'info') and hasattr(tool.info, 'description'):
                    description = tool.info.description or description
                elif tool.__doc__:
                    doc = tool.__doc__
                    description = " ".join(line.strip() for line in doc.split('\n')).strip()
                    
                tool_descriptions[tool_name_upper] = description
                logger.debug(f"Registered tool: {tool_name_upper}")
            else:
                logger.warning(f"Tool '{tool_name_upper}' is not a valid Tool instance and will be skipped.")
        else:
            logger.warning(f"Tool '{tool_name_upper}' configured but not found in TOOL_REGISTRY.")
            tool_descriptions[tool_name_upper] = "(Tool configured but not implemented)"
            
    return configured_tools, tool_descriptions
