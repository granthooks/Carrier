"""
Extensions for the Agent class from the OpenAI Agents SDK.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from agents import Agent


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
    Extended Agent class with Carrier-specific functionality.
    """

    def __init__(self, *args, **kwargs):
        # Extract memory parameter before passing to parent
        self.memory = kwargs.pop('memory', None)
        super().__init__(*args, **kwargs)

    @classmethod
    def from_agent(cls, agent: Agent, memory: Optional[AgentMemory] = None):
        """
        Create a CarrierAgent from an existing Agent instance.
        
        Args:
            agent: An existing Agent instance
            memory: Memory object for the agent
            
        Returns:
            CarrierAgent instance with properties from the original agent
        """
        # Create a dictionary of parameters to pass to the new agent
        kwargs = {
            "name": agent.name,
            "instructions": agent.instructions,
            "model": agent.model,
        }
        
        # Add optional parameters if they exist
        if hasattr(agent, 'tools'):
            kwargs["tools"] = agent.tools
        if hasattr(agent, 'handoffs'):
            kwargs["handoffs"] = agent.handoffs
        if hasattr(agent, 'output_type'):
            kwargs["output_type"] = agent.output_type
        if hasattr(agent, 'model_settings'):
            kwargs["model_settings"] = agent.model_settings
            
        # Add memory parameter
        kwargs["memory"] = memory
            
        # Create new CarrierAgent with parameters
        carrier_agent = cls(**kwargs)
        return carrier_agent
