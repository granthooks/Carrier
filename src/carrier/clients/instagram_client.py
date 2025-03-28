"""
Instagram Client for Carrier Agent Framework

This module contains the InstagramAgentClient for posting media to Instagram
using the Instagram Graph API.
"""

import os
import asyncio
import json
import logging
from typing import Dict, Tuple, Any, Optional
import aiohttp
from ftplib import FTP
from datetime import datetime

from agents import Agent, Runner, RunContextWrapper, RunHooks

from ..utils.logging import configure_logging
from ..utils.hooks_util import add_memory_hooks
from ..extensions.carrier_agent import AgentMemory

# Configure logging
logger = configure_logging()

# base url for instagram api
BASE_URL = "https://graph.instagram.com"

class InstagramHooks(RunHooks):
    """Instagram-specific hooks for the agent runtime"""
    
    def __init__(self):
        self.processed_messages = 0
        self.client = "instagram"
    
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Called when agent processing begins"""
        self.processed_messages += 1
    
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Any) -> None:
        """Called when a tool execution begins"""
        logger.info(f"[{self.client}] Executing tool: {tool.name}")
    
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Any, result: str) -> None:
        """Called when a tool execution completes"""
        logger.info(f"[{self.client}] Tool {tool.name} completed with result: {result}")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when agent processing completes"""
        memory = self._get_memory_from_context(context)
        
        # Store conversation in memory for future context
        if memory and hasattr(output, 'content') and output.content:
            memory.conversation_history.append({
                "role": "assistant",
                "content": output.content,
                "timestamp": "now",  # In a real implementation, use actual timestamp
                "client": self.client
            })
            logger.info(f"[{self.client}] Memory contains {len(memory.conversation_history)} messages")
        
        logger.info(f"[{self.client}] Response generated and stored in memory")
    
    def _get_memory_from_context(self, context: RunContextWrapper) -> Optional[AgentMemory]:
        """Get memory object from context if available."""
        if not context or not context.context:
            return None
            
        # If context is directly a memory object
        if isinstance(context.context, AgentMemory):
            return context.context
            
        # If context has a memory attribute
        if hasattr(context.context, 'memory'):
            return context.context.memory
            
        return None


def get_hooks_with_memory(agent: Agent, user_id: str, room_id: str) -> RunHooks:
    """Get appropriate hooks with memory context if available.
    
    Args:
        agent: Agent to use
        user_id: User ID for memory context
        room_id: Room ID for memory context
        
    Returns:
        Appropriate hooks instance with memory context if available
    """
    return add_memory_hooks(
        base_hooks_class=InstagramHooks,
        agent=agent,
        user_id=user_id,
        room_id=room_id,
        conversation_limit=10,
        client_name="Instagram"
    )


class InstagramAgentClient:
    """Instagram client that manages a single agent interaction"""
    
    def __init__(self, agent: Agent, memory: AgentMemory):
        """Initialize the Instagram client for a specific agent"""
        # Store agent and memory directly
        self.agent = agent
        self.memory = memory
        
        # Instagram API credentials will be passed to run() method
        self.instagram_credentials = None
        
        # FTP credentials for media uploads
        self.ftp_credentials = None
        
        # Client state
        self.is_running = False
        self.post_count = 0
    
    async def run(self, instagram_token: str = None):
        """Run the Instagram client with the provided token"""
        try:
            # Set up Instagram API credentials
            self.instagram_credentials = self._setup_credentials(instagram_token)
            
            # Set up FTP credentials (for media uploads)
            username = self.agent.name.lower().replace(" ", "_")
            self.ftp_credentials = {
                "host": os.getenv(f"{username}.FTP_HOST"),
                "user": os.getenv(f"{username}.FTP_USER"),
                "password": os.getenv(f"{username}.FTP_PASSWORD"),
                "directory": os.getenv(f"{username}.FTP_DIRECTORY", "/media")
            }
            
            # Run the client
            self.is_running = True
            logger.info(f"Instagram client for {self.agent.name} started")
            
            # Main loop for Instagram operations
            while self.is_running:
                # Check for scheduled posts, mentions, or DMs
                # Process with self.agent directly (no lookup needed)
                await self._check_instagram_activities()
                
                # Respect API rate limits
                await asyncio.sleep(60)  # Sleep to avoid hitting rate limits
                
        except Exception as e:
            logger.error(f"Instagram client error for {self.agent.name}: {e}")
            self.is_running = False
    
    def _setup_credentials(self, instagram_token: str):
        """Set up Instagram API credentials"""
        # Implementation of _setup_credentials method
        # This method should return the necessary credentials for the Instagram API
        # based on the provided token.
        # For example, it could return a tuple (account_id, access_token)
        # or a dictionary with the necessary keys.
        # This is a placeholder and should be implemented according to your specific requirements.
        return instagram_token
    
    async def _check_instagram_activities(self):
        """Check for scheduled posts, mentions, or DMs"""
        # Implementation of _check_instagram_activities method
        # This method should implement the logic to check for scheduled posts, mentions, or DMs
        # and process them accordingly.
        # For example, it could use the self.agent to process the activities.
        # This is a placeholder and should be implemented according to your specific requirements.
        pass
    
    async def upload_file_to_ftp(self, file_path):
        """Upload a file to FTP server and return the URL"""
        logger.info(f"Uploading file to FTP server: {file_path}")
        
        # Check if FTP credentials are set
        if not self.ftp_credentials:
            logger.error("FTP credentials not found in environment variables")
            return False
            
        try:
            # Connect to the FTP server
            ftp = FTP(self.ftp_credentials["host"])
            ftp.login(user=self.ftp_credentials["user"], passwd=self.ftp_credentials["password"])
            
            # Upload to this directory
            remote_dir = self.ftp_credentials["directory"]
            logger.info(f"Uploading file to {self.ftp_credentials['host']}{remote_dir}")
            ftp.cwd(remote_dir)
            
            # Open the file in binary mode and upload it
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._upload_file(ftp, file_path))
            
            # Close the FTP connection
            ftp.quit()
            
            # Return the URL of the uploaded file
            file_name = os.path.basename(file_path)
            file_url = f'https://{self.ftp_credentials["host"]}/media/{file_name}'
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
            url = f"{self.instagram_credentials[0]}/media"
            param = {
                'access_token': self.instagram_credentials[1],
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
            url = f"{self.instagram_credentials[0]}/media"
            param = {
                'access_token': self.instagram_credentials[1],
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
            url = f"{self.instagram_credentials[0]}/{container_id}"
            param = {
                'access_token': self.instagram_credentials[1],
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
            url = f"{self.instagram_credentials[0]}/media_publish"
            param = {
                'access_token': self.instagram_credentials[1],
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
            url = f"{BASE_URL}/v22.0/{self.instagram_credentials[0]}/content_publishing_limit"
            param = {
                'access_token': self.instagram_credentials[1]
            }
            
            logger.info(f"URL: {url}")
            logger.info(f"Params: {param}")
            
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
    
    async def get_user_media(self, user_id=None, fields=None):
        """
        Retrieve media from an Instagram account using the Graph API.
        
        Args:
            user_id: The Instagram user ID to retrieve media from (defaults to authenticated user)
            fields: The fields to retrieve (defaults to followers_count and media details)
            
        Returns:
            JSON response with user media data
        """
        logger.info(f"Retrieving media for user: {user_id or 'self'}")
        try:
            # Default to the authenticated user if no user_id provided
            target_id = user_id or self.instagram_credentials[0]
            
            # Default fields if none provided
            if fields is None:
                fields = "followers_count,media{media_type,caption,timestamp,like_count}"
            
            url = f"{BASE_URL}/v22.0/{target_id}"
            params = {
                'fields': fields,
                'access_token': self.instagram_credentials[1]
            }
            
            logger.info(f"URL: {url}")
            logger.info(f"Params: {params}")
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    result = await response.json()
                    logger.info(f"Retrieved media data: {result}")
                    return result
        except Exception as e:
            logger.error(f"Error retrieving user media: {e}")
            return None
