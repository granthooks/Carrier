import json

def _handle_tool_calls(self, response, context):
    tool_calls = response.get("tool_calls", [])
    logger.info(f"ORIGINAL TOOL CALLS: {json.dumps(tool_calls, indent=2)}")
    
    # Rest of the existing code 