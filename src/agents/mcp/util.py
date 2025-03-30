import functools
import json
from typing import TYPE_CHECKING, Any

from .. import _debug
from ..exceptions import AgentsException, ModelBehaviorError, UserError
from ..logger import logger
from ..run_context import RunContextWrapper
from ..tool import FunctionTool, Tool
from ..tracing import FunctionSpanData, get_current_span, mcp_tools_span

if TYPE_CHECKING:
    from mcp.types import Tool as MCPTool

    from .server import MCPServer


class MCPUtil:
    """Set of utilities for interop between MCP and Agents SDK tools."""

    @classmethod
    async def get_all_function_tools(cls, mcp_servers: list["MCPServer"]) -> list["Tool"]:
        """
        Get all function tools from the MCP servers.

        Args:
            mcp_servers: The MCP servers to get tools from.

        Returns:
            A list of valid function tools from all MCP servers.
        """
        # Import the correct Tool base class for type checking
        from agents import Tool
        
        tools: list[Tool] = []
        for server in mcp_servers:
            try:
                # Skip servers that aren't properly initialized
                if not hasattr(server, 'list_tools') or not callable(server.list_tools):
                    logger.warning(f"MCP server '{getattr(server, 'name', 'Unknown')}' doesn't have a valid list_tools method")
                    continue
                    
                mcp_tools = await server.list_tools()
                
                # Add server reference to each tool
                for tool in mcp_tools:
                    # Some MCP implementations might not include server references
                    if not hasattr(tool, "server"):
                        setattr(tool, "server", server)
                    
                for tool in mcp_tools:
                    try:
                        # Convert each MCP tool to a function tool
                        function_tool = cls.to_function_tool(tool)
                        
                        # Verify it's a valid Tool instance before adding
                        if isinstance(function_tool, Tool):
                            tools.append(function_tool)
                        else:
                            logger.warning(f"Skipping invalid tool {getattr(tool, 'name', 'Unknown')} from server {server.name}. " 
                                            f"Type: {type(function_tool)}")
                    except Exception as tool_e:
                        logger.error(f"Error converting tool {getattr(tool, 'name', 'Unknown')} from server {server.name}: {tool_e}")
            except Exception as e:
                logger.error(f"Failed to list tools for MCP server '{getattr(server, 'name', 'Unknown')}': {e}")
        
        logger.info(f"Registered {len(tools)} valid MCP tools from {len(mcp_servers)} servers")
        return tools

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
                    # Add server reference to the tool
                    if not hasattr(tool, "server"):
                        tool.server = server
                        
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

    @classmethod
    def to_function_tool(cls, tool: "MCPTool") -> "Tool":
        """
        Convert an MCP tool to a function tool.

        Args:
            tool: The MCP tool to convert.

        Returns:
            A function tool from the MCP tool.
        """
        from agents import Tool, FunctionTool
        import functools
        import json
        
        # Get tool properties safely
        name = getattr(tool, "name", None)
        description = getattr(tool, "description", "")
        
        # First check for inputSchema, then fall back to parameters
        parameters = getattr(tool, "inputSchema", getattr(tool, "parameters", {}))
        
        if not name:
            raise ValueError("MCP tool is missing a name")
            
        # Get the server from the tool
        server = getattr(tool, "server", None)
        if not server:
            raise ValueError(f"MCP tool {name} is missing server reference")
        
        logger.debug(f"Converting MCP tool {name} to function tool")
        
        # Ensure the schema has all required properties for OpenAI validation
        if not isinstance(parameters, dict):
            logger.warning(f"Tool {name} has invalid parameters type: {type(parameters)}")
            parameters = {"type": "object", "properties": {}, "additionalProperties": False}
        
        # Ensure root level has type and additionalProperties
        if "type" not in parameters:
            parameters["type"] = "object"
        
        # Ensure it has a properties field if it's an object type
        if parameters["type"] == "object" and "properties" not in parameters:
            parameters["properties"] = {}
        
        # Clean up properties according to OpenAI's schema requirements
        property_names = []
        if "properties" in parameters and isinstance(parameters["properties"], dict):
            property_names = list(parameters["properties"].keys())
            for prop_name, prop_schema in parameters["properties"].items():
                if isinstance(prop_schema, dict):
                    # Remove unsupported properties
                    if "default" in prop_schema:
                        logger.debug(f"Removing unsupported 'default' property from {name}.{prop_name}")
                        del prop_schema["default"]
                    
                    # Ensure type exists
                    if "type" not in prop_schema:
                        prop_schema["type"] = "string"  # Default to string if type is missing
                    
                    # If it's an object, ensure it has properties and additionalProperties: false
                    if prop_schema.get("type") == "object":
                        prop_schema["additionalProperties"] = False
                        if "properties" not in prop_schema:
                            prop_schema["properties"] = {}
                        
                        # If the nested object has properties, make them all required
                        if "properties" in prop_schema and isinstance(prop_schema["properties"], dict):
                            nested_props = list(prop_schema["properties"].keys())
                            if nested_props:
                                prop_schema["required"] = nested_props
        
        # Per OpenAI's requirements, all properties must be listed as required
        if parameters["type"] == "object" and property_names:
            parameters["required"] = property_names
        
        # Always set additionalProperties to false at the root level
        parameters["additionalProperties"] = False
        
        # Log the final schema for debugging
        logger.debug(f"Final schema for {name}: {parameters}")
        
        # Create a function tool
        try:
            # Use the existing invoke_mcp_tool method
            on_invoke = functools.partial(cls.invoke_mcp_tool, server, tool)
            
            # Create a FunctionTool instance
            function_tool = FunctionTool(
                name=name,
                description=description,
                params_json_schema=parameters,
                on_invoke_tool=on_invoke,
                strict_json_schema=True,
            )
            
            # Validate the tool
            if not isinstance(function_tool, Tool):
                logger.warning(f"Created tool for {name} is not a Tool instance: {type(function_tool)}")
                raise TypeError(f"Failed to create a valid Tool instance for {name}")
                
            logger.debug(f"Successfully converted {name} to function tool")
            return function_tool
        except Exception as e:
            logger.error(f"Error creating function tool for {name}: {e}")
            raise

    @classmethod
    async def invoke_mcp_tool(
        cls, server: "MCPServer", tool: "MCPTool", context: RunContextWrapper[Any], input_json: str
    ) -> str:
        """Invoke an MCP tool and return the result as a string."""
        try:
            json_data: dict[str, Any] = json.loads(input_json) if input_json else {}
            
            # Get required schema properties for validation
            input_schema = getattr(tool, "inputSchema", getattr(tool, "parameters", {}))
            if isinstance(input_schema, dict) and "required" in input_schema:
                required_props = input_schema["required"]
                missing_props = [prop for prop in required_props if prop not in json_data]
                if missing_props:
                    logger.warning(f"Missing required properties for {tool.name}: {missing_props}")
        except Exception as e:
            if _debug.DONT_LOG_TOOL_DATA:
                logger.debug(f"Invalid JSON input for tool {tool.name}")
            else:
                logger.debug(f"Invalid JSON input for tool {tool.name}: {input_json}")
            raise ModelBehaviorError(
                f"Invalid JSON input for tool {tool.name}: {input_json}"
            ) from e

        if _debug.DONT_LOG_TOOL_DATA:
            logger.debug(f"Invoking MCP tool {tool.name}")
        else:
            logger.debug(f"Invoking MCP tool {tool.name} with input {json_data}")

        try:
            result = await server.call_tool(tool.name, json_data)
        except Exception as e:
            logger.error(f"Error invoking MCP tool {tool.name}: {e}")
            raise AgentsException(f"Error invoking MCP tool {tool.name}: {e}") from e

        if _debug.DONT_LOG_TOOL_DATA:
            logger.debug(f"MCP tool {tool.name} completed.")
        else:
            logger.debug(f"MCP tool {tool.name} returned {result}")

        # The MCP tool result is a list of content items, whereas OpenAI tool outputs are a single
        # string. We'll try to convert.
        if len(result.content) == 1:
            tool_output = result.content[0].model_dump_json()
        elif len(result.content) > 1:
            tool_output = json.dumps([item.model_dump() for item in result.content])
        else:
            logger.error(f"Errored MCP tool result: {result}")
            tool_output = "Error running tool."

        current_span = get_current_span()
        if current_span:
            if isinstance(current_span.span_data, FunctionSpanData):
                current_span.span_data.output = tool_output
                current_span.span_data.mcp_data = {
                    "server": server.name,
                }
            else:
                logger.warning(
                    f"Current span is not a FunctionSpanData, skipping tool output: {current_span}"
                )

        return tool_output
