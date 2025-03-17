#!/usr/bin/env python3
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

# Configure logging
logger = configure_logging()

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
        from ..agents.agent import AgentMemory  # Import here to avoid circular imports
        
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


class InstagramAgentClient:
    """Instagram client that manages media posting to Instagram"""
    
    def __init__(self, agents_mapping: Dict[str, Tuple[Agent, Any]]):
        """Initialize the Instagram client"""
        self.agents_mapping = agents_mapping
        self.is_running = False
        
        # Instagram Graph API credentials from .env
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.instagram_access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_graph_url = "https://graph.instagram.com/"
        
        # FTP credentials from .env
        self.ftp_server = os.getenv("FTP_SERVER")
        self.ftp_username = os.getenv("FTP_USERNAME")
        self.ftp_password = os.getenv("FTP_PASSWORD")
        self.http_server = os.getenv("HTTP_SERVER")
        
        logger.info("Instagram client initialized")
    
    async def connect(self):
        """Connect to Instagram API - simplified since we're using Graph API directly"""
        logger.info("Instagram client connecting...")
        try:
            # Validate that we have the required credentials
            if not self.instagram_account_id or not self.instagram_access_token:
                logger.error("Instagram Graph API credentials not found in environment variables")
                return False
            
            # Quick validation of access token by checking publishing limit
            result = await self.get_publishing_limit()
            if not result or 'error' in result:
                logger.error(f"Failed to validate Instagram access token: {result}")
                return False
                
            self.is_running = True
            logger.info("Instagram client connected successfully")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Instagram: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Instagram API - simplified since we're not maintaining a session"""
        logger.info("Instagram client disconnecting...")
        self.is_running = False
        logger.info("Instagram client disconnected")
    
    async def upload_file_to_ftp(self, file_path):
        """Upload a file to FTP server and return the URL"""
        logger.info(f"Uploading file to FTP server: {file_path}")
        
        # Check if FTP credentials are set
        if not self.ftp_server or not self.ftp_username or not self.ftp_password:
            logger.error("FTP credentials not found in environment variables")
            return False
            
        try:
            # Connect to the FTP server
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
            url = f"{self.instagram_graph_url}v22.0/{self.instagram_account_id}/content_publishing_limit"
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
        if not await self.connect():
            logger.error("Failed to connect to Instagram. Client will not run.")
            return
        
        logger.info("Instagram client started. Ready to post media.")
        
        # Keep the client running
        while self.is_running:
            try:
                # Check publishing limit occasionally
                await self.get_publishing_limit()
                logger.info("Instagram client is active")
                await asyncio.sleep(3600)  # Sleep for an hour
            except Exception as e:
                logger.error(f"Error in Instagram client run loop: {e}")
                await asyncio.sleep(60)
        
        await self.disconnect() 