"""
Extensions for the Agent class from the OpenAI Agents SDK.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from src.agents import Agent
from src.agents.mcp import MCPServer # Import MCPServer for type hinting


@dataclass
class AgentMemory:
    """
    Maintains the agent's memory between interactions.
    """
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_info: Dict[str, Any] = field(default_factory=dict)
    last_topics: List[str] = field(default_factory=list)
    client: str = "generic"  # Track which client the conversation is from


class CarrierAgent(Agent):
    """
    Extended Agent class with Carrier-specific functionality, including memory and tool tracking.
    """
    all_tool_descriptions: Dict[str, str] # Added attribute to store combined tool descriptions

    def __init__(self, *args, **kwargs):
        # Extract memory parameter before passing to parent
        self.memory = kwargs.pop('memory', None)
        # Initialize the new attribute before calling super().__init__
        self.all_tool_descriptions = {} # Initialize as empty dict
        super().__init__(*args, **kwargs)
        # Note: all_tool_descriptions will be populated later in run_agents.py after initialization

    @classmethod
    def from_agent(cls, agent: Agent, memory: AgentMemory) -> "CarrierAgent":
        """Create a CarrierAgent from a standard Agent."""
        try:
            # Create a dictionary of attributes to pass to the new agent
            kwargs = {
                "name": agent.name,
                "instructions": agent.instructions,
                "model": agent.model,
                "tools": agent.tools,
                # "model_settings": agent.model_settings,
                # "handoffs": agent.handoffs,
                "hooks": agent.hooks,
                # "output_type": agent.output_type,
                # "tools_to_final_output": agent.tools_to_final_output,
                "mcp_servers": agent.mcp_servers,
                "memory": memory
            }
            
            # these are optional attributes
            if hasattr(agent, 'handoffs'):
                kwargs["handoffs"] = agent.handoffs
            if hasattr(agent, 'output_type'):
                kwargs["output_type"] = agent.output_type
            if hasattr(agent, 'model_settings'):
                kwargs["model_settings"] = agent.model_settings
            if hasattr(agent, 'tools_to_final_output'):
                kwargs["tools_to_final_output"] = agent.tools_to_final_output
            
            # Create new CarrierAgent with parameters
            carrier_agent = cls(**kwargs)
        except Exception as e:
            print(f"Error creating CarrierAgent from Agent: {e}")
            raise
        
        # Ensure we copy any additional attributes that might have been set
        if hasattr(agent, 'all_tool_descriptions'):
            carrier_agent.all_tool_descriptions = agent.all_tool_descriptions
        
        return carrier_agent
