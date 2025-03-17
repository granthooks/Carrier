"""
Clients Package for the Carrier Agent Framework

This package contains client implementations for various platforms that can interact with the Carrier Agent Framework.
Each client handles the specifics of a platform's communication protocol and translates between the platform and the agent.

Available clients:

This package contains client implementations for various platforms that can interact with the Carrier Agent Framework.
Each client handles the specifics of a platform's communication protocol and translates between the platform and the agent.

Available clients:

interact with the Carrier Agent Framework. Each client handles the specifics of a platform's communication protocol and translates between the platform and the agent.

Available clients:

of its platform's communication protocol and translates between the platform and the agent.
and the agent.

Available clients:
- DiscordAgentClient: Client for Discord integration
- InstagramAgentClient: Client for Instagram media posting

Usage:
from src.clients import DiscordAgentClient, InstagramAgentClient
"""



# Import and expose client classes
from .discord_client import DiscordAgentClient, DiscordHooks
from .instagram_client import InstagramAgentClient, InstagramHooks



# Define package exports
__all__ = [
    'DiscordAgentClient',
    'DiscordHooks',
    'InstagramAgentClient',
    'InstagramHooks',
]

__version__ = [
    '0.1.0'
    'DiscordHooks',
    'InstagramAgentClient',
    'InstagramHooks',
]

# Package metadata
__version__ = '0.1.0'