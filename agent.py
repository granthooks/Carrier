#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from typing import List, Dict, Any, Optional, Tuple, Mapping
from dataclasses import dataclass, field
from dotenv import load_dotenv
import discord
from discord.ext import commands
from instagrapi import Client as InstagrapiClient
from instagrapi.exceptions import ClientLoginRequired
import base64
from datetime import datetime
import aiohttp

# load .env file
load_dotenv()

# Add the src directory to the path so we can import the agents module
sys.path.append(os.path.abspath("src"))

# Import Carrier agent framework
from agents import Agent, Runner, RunContextWrapper, RunHooks, Usage, TResponseInputItem
from agents.tool import function_tool  # Import the function_tool helper
# Import logging utility
from utils.logging import configure_logging

# Configure logging
logger = configure_logging()

# Character file path
character_file = "characters/assistantbot.json"

# Define the weather tool function
@function_tool
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


@dataclass
class AgentMemory:
    """Maintains the agent's memory between interactions"""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_info: Dict[str, Any] = field(default_factory=dict)
    last_topics: List[str] = field(default_factory=list)
    client: str = "generic"  # Track which client the conversation is from
    
    
async def load_character_file(file_path: str) -> Dict[str, Any]:
    """Load and parse the character file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Character file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_system_prompt(character_data: Dict[str, Any], client: str = "generic") -> str:
    """Build a comprehensive system prompt from character data"""
    
    # Start with the basic system prompt
    system_prompt = character_data.get("system", "")
    
    # Add bio information
    bio = character_data.get("bio", [])
    if bio:
        system_prompt += "\n\n## About You\n" + "\n".join([f"- {item}" for item in bio])
    
    # Add background/lore
    lore = character_data.get("lore", [])
    if lore:
        system_prompt += "\n\n## Your Background\n" + "\n".join([f"- {item}" for item in lore])
    
    # Add communication style
    style = character_data.get("style", {})
    all_style = style.get("all", [])
    chat_style = style.get("chat", [])
    
    if all_style or chat_style:
        system_prompt += "\n\n## Your Communication Style\n"
        if all_style:
            system_prompt += "\n".join([f"- {item}" for item in all_style])
        if chat_style:
            system_prompt += "\n" + "\n".join([f"- {item}" for item in chat_style])
    
    # Add conversation examples if available
    examples = character_data.get("messageExamples", [])
    if examples and len(examples) > 0:
        system_prompt += "\n\n## Example Conversations\n"
        for i, example in enumerate(examples[:3]):  # Limit to 3 examples
            system_prompt += f"\nExample {i+1}:\n"
            for message in example:
                role = "User" if message.get("user") != character_data.get("name") else character_data.get("name")
                content = message.get("content", {}).get("text", "")
                system_prompt += f"{role}: {content}\n"
    
    # Add client-specific context
    system_prompt += "\n\n## Client Context\n"
    if client == "discord":
        system_prompt += "- You are interacting in a Discord server.\n"
        system_prompt += "- You'll only respond when someone mentions you by name or tags you.\n"
        system_prompt += "- Keep responses appropriately sized for a chat client.\n"
        system_prompt += "- Remember that many people might be watching this conversation.\n"
    elif client == "instagram":
        system_prompt += "- You are interacting on Instagram via direct messages.\n"
        system_prompt += "- These are usually private one-on-one conversations.\n"
        system_prompt += "- Keep responses concise and engaging for the client.\n"
        system_prompt += "- Users might share images or stories with you, but you can only respond with text.\n"
    
    # Add information about available tools
    system_prompt += "\n\n## Available Tools\n"
    system_prompt += "- You have access to a weather tool that can tell you the current weather.\n"
    system_prompt += "- You can use this tool by calling get_weather() with an optional location parameter.\n"
    system_prompt += "- The weather is always 'sunny' in this implementation.\n"
    system_prompt += "- Example usage: When a user asks about the weather, you can call the get_weather tool and include the result in your response.\n"
    
    return system_prompt


async def initialize_agent(character_file: str, client: str = "generic") -> Tuple[Agent, AgentMemory]:
    """Step 1: Agent Initialization"""
    logger.info(f"Initializing agent from {character_file} for {client}")
    
    # Load the character file
    character_data = await load_character_file(character_file)
    
    # Build the system prompt from character data
    system_prompt = build_system_prompt(character_data, client)
    
    # Initialize the agent
    agent = Agent(
        name=character_data.get("name", "Agent"),
        instructions=system_prompt,
        model=character_data.get("model", "gpt-4o-mini"),
        tools=[GET_WEATHER]  # Use the decorated function directly
    )
    
    # Initialize memory
    memory = AgentMemory(client=client)
    
    #  list tools in uppercase with brackets between each tool
    tools_list = ", ".join([tool.name.upper() for tool in agent.tools])
    logger.info(f"{agent.name} initialized with {tools_list} for {client}")
    return agent, memory


class ClientHooks(RunHooks):
    """Generic hooks for the runtime loop stages during message processing"""
    
    def __init__(self, client: str = "generic"):
        self.processed_messages = 0
        self.client = client
    
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Step 3: Message Processing pipeline begins"""
        self.processed_messages += 1
    
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Any) -> None:
        """Step 5: Action Execution begins"""
        logger.info(f"[{self.client}] Executing tool: {tool.name}")
    
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Any, result: str) -> None:
        """Step 5: Action Execution completes"""
        logger.info(f"[{self.client}] Tool {tool.name} completed with result: {result}")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Step 6: Evaluation and Step 7: Memory Storage complete"""
        memory: AgentMemory = context.context
        
        # Store conversation in memory for future context
        if hasattr(output, 'content') and output.content:
            memory.conversation_history.append({
                "role": "assistant",
                "content": output.content,
                "timestamp": "now",  # In a real implementation, use actual timestamp
                "client": self.client
            })
            logger.info(f"[{self.client}] Memory contains {len(memory.conversation_history)} messages")
        
        logger.info(f"[{self.client}] Response generated and stored in memory")


class DiscordHooks(ClientHooks):
    """Discord-specific hooks"""
    
    def __init__(self):
        super().__init__(client="discord")


class InstagramHooks(ClientHooks):
    """Instagram-specific hooks"""
    
    def __init__(self):
        super().__init__(client="instagram")


class DiscordAgentClient(commands.Bot):
    """Discord client that manages agent interactions"""
    
    def __init__(self, agents_mapping: Dict[str, Tuple[Agent, AgentMemory]]):
        """Initialize the Discord client"""
        # Setup Discord intents (permissions)
        intents = discord.Intents.default()
        intents.message_content = True  # Needed to read message content
        
        # Initialize the bot with a command prefix (for potential commands)
        super().__init__(command_prefix='!', intents=intents)
        
        # Store agent mapping
        self.agents_mapping = agents_mapping
        
        # Set up our event handlers
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Set up event handlers for Discord events"""
        # These event handlers are already bound due to how discord.py works
        # We're just defining them as methods of our class
        pass
    
    async def on_ready(self):
        """Called when the bot has connected to Discord"""
        logger.info(f"Discord bot connected as {self.user}")
        logger.info(f"Available agents on Discord: {', '.join(self.agents_mapping.keys())}")
    
    async def on_message(self, message: discord.Message):
        """Called when a message is received"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if the bot is mentioned
        if self.user.mentioned_in(message):
            await self.process_mention(message)
        
        # Process commands (if we add any)
        await self.process_commands(message)
    
    async def process_mention(self, message: discord.Message):
        """Process a message that mentions the bot"""
        # Extract the message content without the mention
        content = message.clean_content
        
        # Remove the mention of the bot
        for mention in message.mentions:
            if mention == self.user:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        
        content = content.strip()
        
        # Determine which agent to use (default to the first one for now)
        agent_name = self.determine_addressed_agent(message.content)
        
        if agent_name in self.agents_mapping:
            agent, memory = self.agents_mapping[agent_name]
        else:
            # Default to the first agent if no match
            agent_name = list(self.agents_mapping.keys())[0]
            agent, memory = self.agents_mapping[agent_name]
        
        logger.info(f"[Discord] Processing mention for {agent_name}: {content}")
        
        # Process with the agent
        await self.process_with_agent(message, content, agent, memory)
    
    def determine_addressed_agent(self, content: str) -> str:
        """Determine which agent is being addressed in the message"""
        # Simple implementation: check if agent name appears in the message
        # In a more advanced implementation, could use NLP to determine the addressed agent
        for agent_name in self.agents_mapping.keys():
            if agent_name.lower() in content.lower():
                return agent_name
        
        # Default to the first agent
        return list(self.agents_mapping.keys())[0]
    
    async def process_with_agent(self, message: discord.Message, content: str, agent: Agent, memory: AgentMemory):
        """Process a message with the specified agent"""
        # Add message to memory
        memory.conversation_history.append({
            "role": "user",
            "content": content,
            "user_id": str(message.author.id),
            "username": message.author.display_name,
            "timestamp": str(message.created_at),
            "client": "discord"
        })
        
        # Create input items from conversation history
        # For simplicity, we'll just use the current message as input
        input_items = [{"content": content, "role": "user"}]
        
        # Set up hooks
        hooks = DiscordHooks()
        
        # Send typing indicator
        async with message.channel.typing():
            try:
                # Process with agent
                result = await Runner.run(
                    agent,
                    input_items,
                    context=memory,
                    hooks=hooks
                )
                
                # Get response
                response = result.final_output
                
                # Send response to Discord
                await message.channel.send(response)
                
                # Log the agent's response
                logger.info(f"[Discord] Agent {agent.name} response: {response}")
                
                # Update input items for future context
                return result.to_input_list()
            
            except Exception as e:
                logger.error(f"[Discord] Error processing message: {e}")
                await message.channel.send(f"I encountered an error while processing your message. Please try again later.")


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


class InstagramAgentClient:
    """Instagram client that manages media posting to Instagram"""
    
    def __init__(self, agents_mapping: Dict[str, Tuple[Agent, AgentMemory]]):
        """Initialize the Instagram client"""
        self.agents_mapping = agents_mapping
        self.is_running = False
        
        # Instagram API credentials from .env 
        self.username = os.getenv("INSTAGRAM_USERNAME")
        self.password = os.getenv("INSTAGRAM_PASSWORD")
        
        # Instagram Graph API credentials from .env
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.instagram_access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_graph_url = "https://graph.instagram.com/"
        
        # FTP credentials from .env
        self.ftp_server = os.getenv("FTP_SERVER")
        self.ftp_username = os.getenv("FTP_USERNAME")
        self.ftp_password = os.getenv("FTP_PASSWORD")
        self.http_server = os.getenv("HTTP_SERVER")
        
        # Instagram API client
        self.api = None
        
        # Session storage path
        self.session_storage = os.path.join(os.path.dirname(__file__), "instagram_session.json")
        
        logger.info(f"Instagram client initialized for user {self.username}")
    
    async def connect(self):
        """Connect to Instagram API"""
        logger.info("Instagram client connecting...")
        try:
            # Create instagrapi client
            self.api = InstagrapiClient()
            
            # Try to load session if it exists
            if os.path.exists(self.session_storage):
                logger.info("Loading Instagram session from file")
                self.api.load_settings(self.session_storage)
                
                # Try reusing the session
                try:
                    self.api.get_timeline_feed()
                    logger.info("Successfully reused Instagram session")
                except Exception:
                    logger.info("Session expired, logging in again")
                    self.api.login(self.username, self.password)
            else:
                # No session exists, log in with credentials
                logger.info("Logging in to Instagram with credentials")
                self.api.login(self.username, self.password)
                
                # Save session for future use
                session_data = self.api.get_settings()
                with open(self.session_storage, 'w') as f:
                    json.dump(session_data, f)
            
            self.is_running = True
            logger.info("Instagram client connected successfully")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Instagram: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Instagram API"""
        logger.info("Instagram client disconnecting...")
        try:
            if self.api:
                # Save session before logging out
                session_data = self.api.get_settings()
                with open(self.session_storage, 'w') as f:
                    json.dump(session_data, f)
                
                # Logout
                self.api.logout()
                self.api = None
            
            self.is_running = False
            logger.info("Instagram client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from Instagram: {e}")
    
    async def upload_file_to_ftp(self, file_path):
        """Upload a file to FTP server and return the URL"""
        logger.info(f"Uploading file to FTP server: {file_path}")
        try:
            # Connect to the FTP server
            from ftplib import FTP
            ftp = FTP(self.ftp_server)
            ftp.login(user=self.ftp_username, passwd=self.ftp_password)
            
            # Upload to this directory
            remote_dir = '/domains/agntc.io/public_html/media'
            logger.info(f"Uploading file to {self.ftp_server}{remote_dir}")
            ftp.cwd(remote_dir)
            
            # Open the file in binary mode and upload it
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._upload_file(ftp, file_path))
            
            # Close the FTP connection
            ftp.quit()
            
            # Return the URL of the uploaded file
            file_name = os.path.basename(file_path)
            file_url = f'https://{self.http_server}/media/{file_name}'
            logger.info(f"File uploaded successfully. URL: {file_url}")
            return file_url
        except Exception as e:
            logger.error(f"Error uploading file to FTP: {e}")
            return None

    def _upload_file(self, ftp, file_path):
        """Helper method to upload file to FTP (runs in executor)"""
        with open(file_path, 'rb') as file:
            file_name = os.path.basename(file_path)
            ftp.storbinary(f'STOR {file_name}', file)
    
    async def post_media(self, file_url, caption=''):
        """Post media (image or video) to Instagram"""
        logger.info(f"Posting media to Instagram: {file_url}")
        try:
            url = f"{self.instagram_graph_url}{self.instagram_account_id}/media"
            param = {
                'access_token': self.instagram_access_token,
                'caption': caption
            }
            
            if file_url.endswith('.jpg') or file_url.endswith('.jpeg') or file_url.endswith('.png'):
                logger.info("Posting image...")
                param['image_url'] = file_url
            elif file_url.endswith('.mp4'):
                logger.info("Posting video...")
                param['media_type'] = 'REELS'
                param['video_url'] = file_url
                param['share_to_feed'] = 'true'
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=param) as response:
                    result = await response.json()
                    logger.info(f"Media posted with result: {result}")
                    return result
        except Exception as e:
            logger.error(f"Error posting media to Instagram: {e}")
            return None
    
    async def post_reel(self, video_url, media_type='REELS'):
        """Post a reel to Instagram"""
        logger.info(f"Posting reel to Instagram: {video_url}")
        try:
            url = f"{self.instagram_graph_url}{self.instagram_account_id}/media"
            param = {
                'access_token': self.instagram_access_token,
                'video_url': video_url,
                'media_type': media_type,
                'thumb_offset': '10'  # thumbnail offset in milliseconds
            }
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=param) as response:
                    result = await response.json()
                    logger.info(f"Reel posted with result: {result}")
                    return result
        except Exception as e:
            logger.error(f"Error posting reel to Instagram: {e}")
            return None
    
    async def status_of_upload(self, container_id):
        """Check the status of an upload"""
        logger.info(f"Checking status of upload: {container_id}")
        try:
            url = f"{self.instagram_graph_url}{container_id}"
            param = {
                'access_token': self.instagram_access_token,
                'fields': 'status_code, status'
            }
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=param) as response:
                    result = await response.json()
                    logger.info(f"Upload status: {result}")
                    return result
        except Exception as e:
            logger.error(f"Error checking upload status: {e}")
            return None
    
    async def publish_container(self, container_id):
        """Publish a container once it's ready"""
        logger.info(f"Publishing container: {container_id}")
        try:
            url = f"{self.instagram_graph_url}{self.instagram_account_id}/media_publish"
            param = {
                'access_token': self.instagram_access_token,
                'creation_id': container_id
            }
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=param) as response:
                    result = await response.json()
                    logger.info(f"Container published with result: {result}")
                    return result
        except Exception as e:
            logger.error(f"Error publishing container: {e}")
            return None
    
    async def post_to_instagram(self, file_url, caption=''):
        """Post content to Instagram (full process)"""
        logger.info(f"Posting content to Instagram: {file_url}")
        try:
            # Post the media
            response = await self.post_media(file_url=file_url, caption=caption)
            if not response or 'id' not in response:
                logger.error(f"Failed to post media: {response}")
                return None
            
            container_id = response['id']
            logger.info(f"Uploaded media with container_id: {container_id}")
            
            # Check status until ready or timeout
            upload_complete = False
            counter = 0
            while not upload_complete and counter < 25:  # stop after ~2min
                # Check status of uploaded container
                response = await self.status_of_upload(container_id)
                
                if not response:
                    logger.error("Failed to get upload status")
                    break
                    
                if response.get('status_code') == 'FINISHED':
                    logger.info('Upload complete, ready to publish!')
                    upload_complete = True
                else:
                    logger.info(f'Upload not ready. Status: {response.get("status_code", "Unknown")}, {response.get("status", "Unknown")}')
                    logger.info('Waiting 5 seconds...')
                    counter += 1
                    await asyncio.sleep(5)
            
            if upload_complete:
                # Publish the container
                response = await self.publish_container(container_id)
                logger.info(f"Container published: {response}")
                return response
            else:
                logger.error("Upload container to Instagram FAILED or timed out")
                return None
                
        except Exception as e:
            logger.error(f"Error in post_to_instagram: {e}")
            return None
    
    async def get_publishing_limit(self):
        """Get the publishing limit status"""
        logger.info("Getting publishing limit...")
        try:
            url = f"{self.instagram_graph_url}{self.instagram_account_id}/content_publishing_limit"
            param = {
                'access_token': self.instagram_access_token
            }
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=param) as response:
                    result = await response.json()
                    if 'data' in result and len(result['data']) > 0:
                        quota_usage = result['data'][0].get('quota_usage', 'Unknown')
                        logger.info(f"Instagram daily quota usage: {quota_usage}")
                    return result
        except Exception as e:
            logger.error(f"Error getting publishing limit: {e}")
            return None
    
    async def run(self):
        """Run the Instagram client"""
        if not self.username or not self.password:
            logger.error("Instagram credentials not found in environment variables")
            return
        
        if not await self.connect():
            logger.error("Failed to connect to Instagram. Client will not run.")
            return
        
        logger.info("Instagram client started. Ready to post media.")
        
        # Keep the client running to maintain the session
        while self.is_running:
            try:
                # Just keep the session alive, no need to poll for messages
                await asyncio.sleep(60)  # Sleep for a minute
            except Exception as e:
                logger.error(f"Error in Instagram client run loop: {e}")
                await asyncio.sleep(60)
        
        await self.disconnect()


async def main():
    """Main function to run both Discord and Instagram clients"""
    # Load environment variables
    load_dotenv()
    
    # Initialize agents
    agents_mapping_discord = {}
    agents_mapping_instagram = {}
    
    # Initialize Assistant Bot agent for Discord and Instagram
    try:
        assistantbot_agent_discord, assistantbot_memory_discord = await initialize_agent(
            character_file, 
            client="Discord"
        )
        agents_mapping_discord[assistantbot_agent_discord.name] = (assistantbot_agent_discord, assistantbot_memory_discord)
        
        # Initialize Assistant Bot agent for Instagram
        assistantbot_agent_instagram, assistantbot_memory_instagram = await initialize_agent(
            character_file, 
            client="Instagram"
        )
        agents_mapping_instagram[assistantbot_agent_instagram.name] = (assistantbot_agent_instagram, assistantbot_memory_instagram)
        
    except Exception as e:
        logger.error(f"Error initializing agents: {e}")
        return
    
    # Create the clients
    discord_client = DiscordAgentClient(agents_mapping_discord)
    instagram_client = InstagramAgentClient(agents_mapping_instagram)
    
    # Create tasks to run both clients concurrently
    discord_task = asyncio.create_task(discord_client.start(os.getenv("DISCORD_API_TOKEN")))
    instagram_task = asyncio.create_task(instagram_client.run())
    
    # Wait for both tasks to complete (they should run indefinitely unless there's an error)
    try:
        logger.info("Starting Discord and Instagram clients...")
        await asyncio.gather(discord_task, instagram_task)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"Error running clients: {e}")
    finally:
        # This will only run if the clients are stopped
        logger.info("Closing client connections...")
        
        # Properly close Discord connection
        if not discord_client.is_closed():
            await discord_client.close()
        
        # Stop Instagram client
        instagram_client.is_running = False


if __name__ == "__main__":
    # Run the asyncio event loop
    asyncio.run(main())