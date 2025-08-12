#!/usr/bin/env python3
"""
Consolidated Slack Bridge - Single file daemon
Combines all daemon functionality with color-based agent identification
"""
import asyncio
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta

# External dependencies
import aiohttp
from aiohttp import web, ClientSession
from aiohttp.web import Request, Response, json_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def replace_agent_mentions(text: str, agent_configs: Dict) -> str:
    """
    Replace @agent-name mentions with proper Slack user ID mentions
    Example: @agent-sam -> <@U096VLDAHJ5>
    Case-insensitive matching
    """
    import re
    
    for color, config in agent_configs.items():
        name = config.get("name", "")
        user_id = config.get("bot_user_id", "")
        
        if name and user_id:
            # Case-insensitive replacement of @agent-name
            pattern = f"@{re.escape(name)}"
            replacement = f"<@{user_id}>"
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def filter_relevant_messages_for_agent(messages, agent_identifier, exclude_reacted=True, bot_user_id=None):
    """Filter messages for relevance to a specific agent (color or name)"""
    relevant = []
    
    # Keywords that indicate team-wide relevance
    team_keywords = [
        "@here", "@channel", "@everyone",
        "all agents", "team meeting", "system alert", 
        "critical", "emergency", "deployment", "outage",
        "maintenance", "daemon restart"
    ]
    
    # Look for proper Slack user ID mentions: <@U096VLDAHJ5>
    user_id_pattern = f"<@{bot_user_id}>" if bot_user_id else None
    
    # Legacy: Support old text-based patterns for backwards compatibility
    agent_patterns = [
        f"@{agent_identifier.lower()}",     # @red or @agent-sam
        f"[{agent_identifier.lower()}]",    # [red] or [agent-sam]
        f"{agent_identifier.lower()}:"      # red: or agent-sam:
    ]
    
    for msg in messages:
        text = msg.get("text", "")
        text_lower = text.lower()
        
        # Check if this specific agent has already reacted to this message
        if exclude_reacted and bot_user_id:
            reactions = msg.get("reactions", [])
            agent_reacted = False
            
            for reaction in reactions:
                users = reaction.get("users", [])
                if bot_user_id in users:
                    agent_reacted = True
                    break
            
            if agent_reacted:
                continue
        
        # Check for team-wide alerts first
        if any(keyword.lower() in text_lower for keyword in team_keywords):
            relevant.append(msg)
            continue
            
        # Check for proper Slack user ID mentions first (preferred)
        if user_id_pattern and user_id_pattern in text:
            relevant.append(msg)
            continue
            
        # Fallback: Check for legacy text-based patterns
        if any(pattern in text_lower for pattern in agent_patterns):
            relevant.append(msg)
            
    return relevant

class SlackAPIClient:
    """Slack API client with rate limiting and error handling"""
    
    def __init__(self, bot_token: str, app_token: str, rate_limit_config: Dict):
        self.bot_token = bot_token
        self.app_token = app_token
        self.base_url = "https://slack.com/api"
        
        # Rate limiting
        self.rate_limit = rate_limit_config
        self.call_history = []
        self.message_history = []
        
        # Cache
        self.channels_cache = {}
        self.users_cache = {}
        self.cache_expiry = timedelta(minutes=5)
        self.last_cache_update = None
        
        # Session
        self.session = None
        
    def _check_rate_limit(self, endpoint_type: str) -> bool:
        """Check if we're within rate limits"""
        now = time.time()
        minute_ago = now - 60
        
        if endpoint_type == "message":
            # Clean old entries
            self.message_history = [t for t in self.message_history if t > minute_ago]
            
            if len(self.message_history) >= self.rate_limit["messages_per_minute"]:
                return False
            
            self.message_history.append(now)
            return True
        else:
            # General API calls
            self.call_history = [t for t in self.call_history if t > minute_ago]
            
            if len(self.call_history) >= self.rate_limit["api_calls_per_minute"]:
                return False
            
            self.call_history.append(now)
            return True
    
    async def _wait_for_rate_limit(self, endpoint_type: str):
        """Wait until we can make another call"""
        while not self._check_rate_limit(endpoint_type):
            await asyncio.sleep(1)
    
    async def _make_request(self, endpoint: str, method: str = "POST", data = None, endpoint_type: str = "api") -> Dict:
        """Make authenticated request to Slack API"""
        await self._wait_for_rate_limit(endpoint_type)
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.bot_token}"
        }
        
        # DEBUG: Log request details
        logger.info(f"Making {method} request to {endpoint}")
        logger.info(f"Request data: {data}")
        
        # Check if data is FormData (for file uploads)
        import aiohttp
        is_form_data = isinstance(data, aiohttp.FormData)
        
        if not is_form_data:
            headers["Content-Type"] = "application/json"
        
        try:
            if method == "POST":
                if is_form_data:
                    # For file uploads, use FormData directly
                    async with self.session.post(url, headers=headers, data=data) as response:
                        result = await response.json()
                else:
                    # For regular API calls - check if endpoint requires form data
                    if endpoint == "files.getUploadURLExternal":
                        # This endpoint expects form data, not JSON
                        headers.pop("Content-Type", None)  # Let aiohttp set the correct content-type
                        async with self.session.post(url, headers=headers, data=data) as response:
                            result = await response.json()
                    else:
                        # Regular JSON API calls (including files.completeUploadExternal)
                        async with self.session.post(url, headers=headers, json=data) as response:
                            result = await response.json()
            else:
                async with self.session.get(url, headers=headers, params=data) as response:
                    result = await response.json()
            
            # DEBUG: Log response
            logger.info(f"Response from {endpoint}: {result}")
            
            if not result.get("ok"):
                logger.error(f"Slack API error: {result.get('error')}")
                raise Exception(f"Slack API error: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Request to {endpoint} failed: {e}")
            raise
    
    async def send_message(self, text: str, channel: str) -> Dict:
        """Send a message to a channel"""
        data = {
            "channel": channel,
            "text": text
        }
        
        result = await self._make_request("chat.postMessage", data=data, endpoint_type="message")
        return {
            "success": True,
            "timestamp": result.get("ts"),
            "channel": result.get("channel")
        }
    
    async def get_messages(self, channel: str, limit: int = 50, since_timestamp: Optional[float] = None) -> List[Dict]:
        """Get recent messages from a channel"""
        params = {
            "channel": channel,
            "limit": limit
        }
        
        if since_timestamp:
            params["oldest"] = str(since_timestamp)
        
        result = await self._make_request("conversations.history", method="GET", data=params)
        
        messages = []
        for msg in result.get("messages", []):
            if msg.get("type") == "message" and not msg.get("hidden"):
                # Get user info
                user_id = msg.get("user")
                user_name = await self._get_user_name(user_id) if user_id else "Unknown"
                
                messages.append({
                    "timestamp": msg.get("ts"),
                    "user_id": user_id,
                    "user_name": user_name,
                    "text": msg.get("text", ""),
                    "channel": channel,
                    "reactions": msg.get("reactions", []),
                    "files": msg.get("files", [])
                })
        
        return messages
    
    async def add_reaction(self, channel: str, timestamp: str, emoji: str) -> Dict:
        """Add a reaction to a message"""
        data = {
            "channel": channel,
            "timestamp": timestamp,
            "name": emoji
        }
        
        await self._make_request("reactions.add", data=data)
        return {"success": True}
    
    async def get_channels(self) -> List[Dict]:
        """Get list of channels"""
        await self._update_cache_if_needed()
        
        channels = []
        for channel_id, channel_info in self.channels_cache.items():
            channels.append({
                "id": channel_id,
                "name": channel_info["name"],
                "is_public": not channel_info.get("is_private", False)
            })
        
        return channels
    
    async def _get_user_name(self, user_id: str) -> str:
        """Get user display name from cache or API"""
        await self._update_cache_if_needed()
        
        user_info = self.users_cache.get(user_id)
        if user_info:
            return user_info.get("display_name") or user_info.get("real_name") or user_info.get("name", "Unknown")
        
        return "Unknown"
    
    async def _update_cache_if_needed(self):
        """Update channels and users cache if expired"""
        now = datetime.now()
        
        if (self.last_cache_update is None or 
            now - self.last_cache_update > self.cache_expiry):
            
            await self._update_channels_cache()
            await self._update_users_cache()
            self.last_cache_update = now
    
    async def _update_channels_cache(self):
        """Update channels cache"""
        try:
            result = await self._make_request("conversations.list", method="GET", data={"types": "public_channel"})
            
            self.channels_cache = {}
            for channel in result.get("channels", []):
                self.channels_cache[channel["id"]] = {
                    "name": channel.get("name"),
                    "is_private": channel.get("is_private", False)
                }
                
        except Exception as e:
            logger.error(f"Failed to update channels cache: {e}")
    
    async def _update_users_cache(self):
        """Update users cache"""
        try:
            result = await self._make_request("users.list", method="GET")
            
            self.users_cache = {}
            for user in result.get("members", []):
                profile = user.get("profile", {})
                self.users_cache[user["id"]] = {
                    "name": user.get("name"),
                    "real_name": user.get("real_name"),
                    "display_name": profile.get("display_name")
                }
                
        except Exception as e:
            logger.error(f"Failed to update users cache: {e}")
    
    async def upload_file(self, file_data: bytes, filename: str, comment: str = "", channel: str = None) -> Dict:
        """Upload a file to Slack using files.uploadV2"""
        import aiohttp
        
        logger.info(f"Starting file upload: {filename} ({len(file_data)} bytes) to channel {channel}")
        
        # Step 1: Get upload URL
        upload_params = {
            "filename": filename,
            "length": len(file_data)
        }
        
        logger.info(f"Getting upload URL with params: {upload_params}")
        upload_info = await self._make_request("files.getUploadURLExternal", data=upload_params, endpoint_type="file")
        upload_url = upload_info.get("upload_url")
        file_id = upload_info.get("file_id")
        
        if not upload_url or not file_id:
            logger.error(f"Upload URL response: {upload_info}")
            raise ValueError("Failed to get upload URL from Slack")
        
        logger.info(f"Got upload URL and file_id: {file_id}")
        
        # Step 2: Upload file to the URL
        async with self.session.post(upload_url, data=file_data) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(f"File upload failed: {response.status} - {response_text}")
                raise ValueError(f"Failed to upload file: {response.status}")
        
        logger.info("File uploaded successfully, completing...")
        
        # Step 3: Complete the upload
        complete_params = {
            "files": [{"id": file_id, "title": filename}]
        }
        
        if channel:
            complete_params["channel_id"] = channel
        if comment:
            complete_params["initial_comment"] = comment
        
        logger.info(f"Completing upload with params: {complete_params}")
        result = await self._make_request("files.completeUploadExternal", data=complete_params, endpoint_type="file")
        
        return {
            "success": True,
            "file_id": file_id,
            "files": result.get("files", [])
        }
    
    async def list_files(self, channel: str = None, limit: int = 100) -> Dict:
        """List files from Slack"""
        params = {"count": limit}
        if channel:
            params["channel"] = channel
        
        result = await self._make_request("files.list", method="GET", data=params)
        
        files = []
        for file_info in result.get("files", []):
            files.append({
                "id": file_info.get("id"),
                "name": file_info.get("name"),
                "title": file_info.get("title"),
                "mimetype": file_info.get("mimetype"),
                "size": file_info.get("size"),
                "url": file_info.get("url_private"),
                "created": file_info.get("created"),
                "user": file_info.get("user")
            })
        
        return {"files": files}
    
    async def download_file(self, file_id: str) -> Dict:
        """Download a file from Slack"""
        # First get file info
        result = await self._make_request("files.info", method="GET", data={"file": file_id})
        file_info = result.get("file", {})
        
        if not file_info:
            raise ValueError(f"File {file_id} not found")
        
        # Download the file content
        url = file_info.get("url_private")
        if not url:
            raise ValueError(f"No download URL for file {file_id}")
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    content = await response.read()
                    import base64
                    return {
                        "success": True,
                        "filename": file_info.get("name"),
                        "content": base64.b64encode(content).decode('utf-8'),
                        "mimetype": file_info.get("mimetype")
                    }
                else:
                    raise ValueError(f"Failed to download file: {response.status}")
    
    async def delete_file(self, file_id: str) -> Dict:
        """Delete a file from Slack"""
        result = await self._make_request("files.delete", data={"file": file_id}, endpoint_type="file")
        return {"success": True}


class HTTPServer:
    """HTTP REST Server for Slack Daemon"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = None
        self.runner = None
        self.site = None
        self.handlers = {}
        
        # Server configuration
        self.host = config.get("daemon", {}).get("host", "127.0.0.1")
        # Use port discovery if no port specified
        configured_port = config.get("daemon", {}).get("port")
        if configured_port:
            self.port = configured_port
        else:
            self.port = self._discover_available_port()
            logger.info(f"Port discovery found available port: {self.port}")
    
    def _discover_available_port(self) -> int:
        """
        Discover an available port using project-based derivation with fallback
        """
        import hashlib
        import socket
        import os
        
        # PRODUCTION PORT CONFIGURATION
        # Port ranges are used to isolate different environments and allow multiple instances
        # 
        # PRODUCTION RANGE: 19842-19941 (100 ports)
        #   - Used for live/production puente instances  
        #   - Located in: puente/ directory
        #   - Wider range supports more concurrent projects
        #
        # TEST RANGE: 19950-19999 (50 ports) 
        #   - Used for development/testing puente instances
        #   - Located in: puenteserver/, puenteclient/ directories
        #   - Isolated from production to prevent conflicts
        #
        # Port Selection Logic:
        #   1. Hash project directory path (ensures consistency across server/client)
        #   2. Calculate offset: hash % PORT_RANGE_SIZE  
        #   3. Final port: BASE_PORT + offset
        #   4. If unavailable, scan range for next free port
        
        BASE_PORT = 19842  # PRODUCTION range start
        PORT_RANGE_SIZE = 1000  # PRODUCTION range: 19842-20841 (1000 slots)
        MAX_PORT = BASE_PORT + PORT_RANGE_SIZE - 1
        
        def get_project_port(project_path: str) -> int:
            """Derive consistent port from project path hash"""
            path_hash = hashlib.md5(str(project_path).encode('utf-8')).hexdigest()
            hash_int = int(path_hash[:8], 16)
            port_offset = hash_int % PORT_RANGE_SIZE
            return BASE_PORT + port_offset
        
        def is_port_available(port: int) -> bool:
            """Check if a port is available for binding"""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(('127.0.0.1', port))
                    return True
            except OSError:
                return False
        
        # Get project root directory for port calculation
        project_path = os.getcwd()
        
        # Try hash-based port first, then increment until free port found
        derived_port = get_project_port(project_path)
        
        # Find first available port starting from derived port
        port = derived_port
        while not is_port_available(port):
            port += 1
            # Safety check to prevent infinite loop
            if port > BASE_PORT + PORT_RANGE_SIZE:
                raise RuntimeError(f"Cannot find available port in range {BASE_PORT}-{BASE_PORT + PORT_RANGE_SIZE}")
        
        # Write the actual port to .puente/port file for client discovery
        port_file_path = os.path.join(os.getcwd(), 'port')
        try:
            with open(port_file_path, 'w') as f:
                f.write(str(port))
        except Exception as e:
            raise RuntimeError(f"Failed to write port file {port_file_path}: {e}")
            
        return port
        
    async def start(self):
        """Start HTTP server"""
        try:
            logger.info("Starting HTTP server initialization...")
            self.app = web.Application()
            
            # Setup routes
            self._setup_routes()
            
            # Start server
            logger.info(f"Starting HTTP server on {self.host}:{self.port}...")
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"HTTP server started on http://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            raise
        
    async def stop(self):
        """Stop HTTP server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("HTTP server stopped")
    
    def _setup_routes(self):
        """Setup HTTP routes"""
        # Slack API endpoints
        self.app.router.add_post('/send_message', self._handle_send_message)
        self.app.router.add_get('/get_messages', self._handle_get_messages)
        self.app.router.add_get('/get_relevant_messages', self._handle_get_relevant_messages)
        self.app.router.add_post('/add_reaction', self._handle_add_reaction)
        self.app.router.add_get('/get_channels', self._handle_get_channels)
        
        # File operation endpoints
        self.app.router.add_post('/upload_file', self._handle_upload_file)
        self.app.router.add_get('/list_files', self._handle_list_files)
        self.app.router.add_get('/download_file', self._handle_download_file)
        self.app.router.add_post('/delete_file', self._handle_delete_file)
        
        # Daemon management endpoints
        self.app.router.add_get('/health', self._handle_health_check)
        
    def register_handler(self, method: str, handler: Callable):
        """Register a handler for a specific method"""
        self.handlers[method] = handler
    
    async def _handle_send_message(self, request: Request) -> Response:
        """Handle send_message POST request"""
        try:
            if request.content_type == 'application/json':
                params = await request.json()
            else:
                params = dict(await request.post())
                if not params:
                    params = dict(request.query)
            
            if "slack.send_message" in self.handlers:
                result = await self.handlers["slack.send_message"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_get_messages(self, request: Request) -> Response:
        """Handle get_messages GET request"""
        try:
            params = {
                "channel": request.query.get("channel"),
                "limit": int(request.query.get("limit", 50)),
                "since_timestamp": request.query.get("since_timestamp"),
                "agent_color": request.query.get("agent_color")
            }
            
            params = {k: v for k, v in params.items() if v is not None}
            
            if "slack.get_messages" in self.handlers:
                result = await self.handlers["slack.get_messages"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in get_messages: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_get_relevant_messages(self, request: Request) -> Response:
        """Handle get_relevant_messages GET request"""
        try:
            params = {
                "agent_color": request.query.get("agent_color"),
                "channel": request.query.get("channel"),
                "limit": int(request.query.get("limit", 50)),
                "since_timestamp": request.query.get("since_timestamp"),
                "exclude_reacted": request.query.get("exclude_reacted", "true").lower() == "true"
            }
            
            if not params["agent_color"]:
                return json_response({"error": "agent_color parameter is required"}, status=400)
            
            params = {k: v for k, v in params.items() if v is not None}
            
            if "slack.get_relevant_messages" in self.handlers:
                result = await self.handlers["slack.get_relevant_messages"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in get_relevant_messages: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_add_reaction(self, request: Request) -> Response:
        """Handle add_reaction POST request"""
        try:
            if request.content_type == 'application/json':
                params = await request.json()
            else:
                params = dict(await request.post())
            
            if "slack.add_reaction" in self.handlers:
                result = await self.handlers["slack.add_reaction"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in add_reaction: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_get_channels(self, request: Request) -> Response:
        """Handle get_channels GET request"""
        try:
            params = {"agent_color": request.query.get("agent_color")}
            
            if "slack.get_channels" in self.handlers:
                result = await self.handlers["slack.get_channels"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in get_channels: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_health_check(self, request: Request) -> Response:
        """Handle health check GET request"""
        try:
            params = {}
            
            if "daemon.health_check" in self.handlers:
                result = await self.handlers["daemon.health_check"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in health_check: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_upload_file(self, request: Request) -> Response:
        """Handle upload_file POST request"""
        try:
            # Handle multipart form data for file uploads
            reader = await request.multipart()
            params = {}
            file_data = None
            filename = None
            
            async for field in reader:
                if field.name == 'file':
                    file_data = await field.read()
                    filename = field.filename
                else:
                    params[field.name] = await field.text()
            
            if not file_data:
                return json_response({"error": "No file provided"}, status=400)
            
            # Add file data to params
            params['file_data'] = file_data
            params['filename'] = filename
            
            if "slack.upload_file" in self.handlers:
                result = await self.handlers["slack.upload_file"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in upload_file: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_list_files(self, request: Request) -> Response:
        """Handle list_files GET request"""
        try:
            params = {
                "agent_color": request.query.get("agent_color"),
                "channel": request.query.get("channel"),
                "limit": int(request.query.get("limit", 100))
            }
            
            params = {k: v for k, v in params.items() if v is not None}
            
            if "slack.list_files" in self.handlers:
                result = await self.handlers["slack.list_files"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in list_files: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_download_file(self, request: Request) -> Response:
        """Handle download_file GET request"""
        try:
            params = {
                "agent_color": request.query.get("agent_color"),
                "file_id": request.query.get("file_id")
            }
            
            if not params["file_id"]:
                return json_response({"error": "file_id parameter is required"}, status=400)
            
            params = {k: v for k, v in params.items() if v is not None}
            
            if "slack.download_file" in self.handlers:
                result = await self.handlers["slack.download_file"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in download_file: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_delete_file(self, request: Request) -> Response:
        """Handle delete_file POST request"""
        try:
            if request.content_type == 'application/json':
                params = await request.json()
            else:
                params = dict(await request.post())
            
            if not params.get("file_id"):
                return json_response({"error": "file_id parameter is required"}, status=400)
            
            if "slack.delete_file" in self.handlers:
                result = await self.handlers["slack.delete_file"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in delete_file: {e}")
            return json_response({"error": str(e)}, status=500)


class SlackDaemon:
    """Main Slack daemon with color-based agent management"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.slack_clients = {}  # Color-based clients: {"red": client, "blue": client}
        self.agent_configs = {}  # Color-based configs: {"red": config, "blue": config}
        self.http_server = None
        self.is_running = False
        
        # Default channel from config
        self.default_channel = None
        
    async def load_config(self):
        """Load configuration from unified config file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
                
            # Setup logging
            log_config = self.config.get("logging", {})
            log_level = getattr(logging, log_config.get("level", "INFO"))
            
            if log_file := log_config.get("file"):
                logging.basicConfig(
                    level=log_level,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(log_file),
                        logging.StreamHandler()
                    ]
                )
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
            # Load color-based agent configurations
            agents_config = self.config.get("agents", {})
            for color, agent_config in agents_config.items():
                self.agent_configs[color] = agent_config
                logger.info(f"Loaded config for {color} agent ({agent_config.get('name', 'Unknown')})")
            
            logger.info(f"Loaded {len(self.agent_configs)} agent configurations")
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def get_agent_by_identifier(self, identifier: str) -> Optional[str]:
        """Get agent color by name or color identifier"""
        if not identifier:
            return None
            
        # If it's already a color, return it
        if identifier.lower() in self.agent_configs:
            return identifier.lower()
        
        # Check backwards compatibility mapping
        compat_mapping = self.config.get("backwards_compatibility", {}).get("agent_name_to_color", {})
        return compat_mapping.get(identifier)
    
    def get_agent_name_by_color(self, color: str) -> str:
        """Get agent display name by color"""
        agent_config = self.agent_configs.get(color, {})
        return agent_config.get("name", f"Agent-{color.title()}")
    
    async def start(self):
        """Start the daemon"""
        await self.load_config()
        
        # Initialize Slack clients for each color-based agent
        rate_config = self.config["rate_limiting"]
        
        # Set default channel
        self.default_channel = self.config.get("daemon", {}).get("default_channel")
        
        # Create Slack clients for each color-based agent
        for color, agent_config in self.agent_configs.items():
            bot_token = agent_config.get("bot_token")
            
            if bot_token:
                self.slack_clients[color] = SlackAPIClient(
                    bot_token=bot_token,
                    app_token=None,  # Not needed for REST API approach
                    rate_limit_config=rate_config
                )
                logger.info(f"Created Slack client for {color} agent ({agent_config.get('name')})")
            else:
                logger.warning(f"No bot token found for {color} agent")
        
        # Initialize HTTP server
        if self.config.get("daemon", {}).get("enabled", True):
            self.http_server = HTTPServer(self.config)
        else:
            raise RuntimeError("HTTP server is disabled but required for operation")
        
        # Register handlers with HTTP server
        self._register_handlers()
        
        # Start HTTP server
        await self.http_server.start()
        logger.info(f"HTTP server available at http://{self.http_server.host}:{self.http_server.port}")
        
        # Manually start Slack client sessions
        for color, client in self.slack_clients.items():
            client.session = aiohttp.ClientSession()
            logger.info(f"Started session for {color} agent")
        
        self.is_running = True
        logger.info("Slack daemon started successfully")
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Keep running
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()    
    
    async def stop(self):
        """Stop the daemon"""
        logger.info("Stopping Slack daemon...")
        self.is_running = False
        
        if self.http_server:
            await self.http_server.stop()
        
        # Close all Slack client sessions
        for color, client in self.slack_clients.items():
            if client and client.session:
                await client.session.close()
                logger.info(f"Closed session for {color} agent")
                
        logger.info("Slack daemon stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _register_handlers(self):
        """Register JSON-RPC method handlers with color-based agent support"""
        
        def get_slack_client(agent_identifier=None):
            """Get the appropriate Slack client for an agent (by color or name)"""
            if agent_identifier:
                color = self.get_agent_by_identifier(agent_identifier)
                if color and color in self.slack_clients:
                    return self.slack_clients[color]
            
            # Return any available client as fallback
            if self.slack_clients:
                return next(iter(self.slack_clients.values()))
            else:
                raise ValueError("No Slack client available")
        
        async def send_message(params: Dict) -> Dict:
            """Send a message to Slack"""
            try:
                logger.info(f"send_message called with params: {params}")
                text = params.get("text", "")
                channel = params.get("channel", self.default_channel)
                agent_identifier = params.get("agent_color") or params.get("agent_name")  # Support both
                
                if not channel:
                    raise ValueError("No channel specified and no default channel configured")
                
                # Replace @agent-name mentions with proper Slack user IDs
                original_text = text
                text = replace_agent_mentions(text, self.agent_configs)
                
                if text != original_text:
                    logger.info(f"Replaced mentions in message: {original_text[:50]}... -> {text[:50]}...")
                
                logger.info(f"Sending message to {channel} as {agent_identifier}: {text[:50]}...")
                
                # Get appropriate Slack client
                slack_client = get_slack_client(agent_identifier)
                
                if not slack_client:
                    logger.error("No Slack client available!")
                    raise ValueError("Slack client not available")
                
                result = await slack_client.send_message(text, channel)
                logger.info(f"Message sent successfully: {result}")
                
                return result
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise
        
        async def get_messages(params: Dict) -> Dict:
            """Get messages from Slack"""
            channel = params.get("channel", self.default_channel)
            limit = params.get("limit", 50)
            since_timestamp = params.get("since_timestamp")
            agent_identifier = params.get("agent_color") or params.get("agent_name")
            
            if not channel:
                raise ValueError("No channel specified and no default channel configured")
            
            # Get appropriate Slack client
            slack_client = get_slack_client(agent_identifier)
            
            messages = await slack_client.get_messages(
                channel=channel,
                limit=limit,
                since_timestamp=since_timestamp
            )
            
            return {"messages": messages}
        
        async def add_reaction(params: Dict) -> Dict:
            """Add a reaction to a message"""
            channel = params.get("channel", self.default_channel)
            timestamp = params.get("timestamp")
            emoji = params.get("emoji")
            agent_identifier = params.get("agent_color") or params.get("agent_name")
            
            if not all([channel, timestamp, emoji]):
                raise ValueError("Missing required parameters: channel, timestamp, emoji")
            
            # Get appropriate Slack client
            slack_client = get_slack_client(agent_identifier)
            
            result = await slack_client.add_reaction(channel, timestamp, emoji)
            return result
        
        async def get_channels(params: Dict) -> Dict:
            """Get list of channels"""
            agent_identifier = params.get("agent_color") or params.get("agent_name")
            
            # Get appropriate Slack client
            slack_client = get_slack_client(agent_identifier)
            
            channels = await slack_client.get_channels()
            return {"channels": channels}
        
        async def get_relevant_messages(params: Dict) -> Dict:
            """Get messages relevant to a specific agent"""
            agent_identifier = params.get("agent_color") or params.get("agent_name")
            limit = params.get("limit", 50)
            since_timestamp = params.get("since_timestamp")
            channel = params.get("channel", self.default_channel)
            exclude_reacted = params.get("exclude_reacted", True)
            
            if not agent_identifier:
                raise ValueError("agent_color or agent_name parameter is required")
            
            if not channel:
                raise ValueError("No channel specified and no default channel configured")
            
            # Get appropriate Slack client
            slack_client = get_slack_client(agent_identifier)
            
            # Get the bot user ID for this specific agent
            color = self.get_agent_by_identifier(agent_identifier)
            agent_config = self.agent_configs.get(color, {}) if color else {}
            bot_user_id = agent_config.get("bot_user_id")
            
            # Get more messages than requested to have enough to filter from
            fetch_limit = min(limit * 3, 200)  # Fetch 3x requested, max 200
            
            messages = await slack_client.get_messages(
                channel=channel,
                limit=fetch_limit,
                since_timestamp=since_timestamp
            )
            
            # Filter for relevance to the agent
            relevant_messages = filter_relevant_messages_for_agent(
                messages, agent_identifier, exclude_reacted, bot_user_id
            )
            
            # Limit to requested amount
            relevant_messages = relevant_messages[:limit]
            
            return {
                "messages": relevant_messages,
                "agent_identifier": agent_identifier,
                "agent_color": color,
                "total_filtered": len(relevant_messages),
                "searched_total": len(messages),
                "exclude_reacted": exclude_reacted,
                "bot_user_id": bot_user_id
            }
        
        async def upload_file(params: Dict) -> Dict:
            """Upload a file to Slack"""
            try:
                # DEBUG: Log all received parameters
                logger.info(f"Upload request parameters: {list(params.keys())}")
                logger.info(f"Channel: {params.get('channel')}, Default: {self.default_channel}")
                logger.info(f"Agent: {params.get('agent_color')}")
                logger.info(f"Filename: {params.get('filename')}")
                logger.info(f"Comment: {params.get('comment')}")
                logger.info(f"File data size: {len(params.get('file_data', []))}")
                
                file_data = params.get("file_data")
                filename = params.get("filename")
                comment = params.get("comment", "")
                channel = params.get("channel", self.default_channel)
                agent_identifier = params.get("agent_color") or params.get("agent_name")
                
                if not file_data:
                    raise ValueError("No file data provided")
                if not filename:
                    raise ValueError("No filename provided")
                if not channel:
                    raise ValueError("No channel specified and no default channel configured")
                
                # Get appropriate Slack client
                slack_client = get_slack_client(agent_identifier)
                if not slack_client:
                    raise ValueError("Slack client not available")
                
                logger.info(f"Attempting upload with Slack client for {agent_identifier}")
                result = await slack_client.upload_file(file_data, filename, comment, channel)
                return result
            except Exception as e:
                logger.error(f"Failed to upload file: {e}")
                raise
        
        async def list_files(params: Dict) -> Dict:
            """List files from Slack"""
            try:
                channel = params.get("channel")
                limit = params.get("limit", 100)
                agent_identifier = params.get("agent_color") or params.get("agent_name")
                
                # Get appropriate Slack client
                slack_client = get_slack_client(agent_identifier)
                if not slack_client:
                    raise ValueError("Slack client not available")
                
                result = await slack_client.list_files(channel, limit)
                return result
            except Exception as e:
                logger.error(f"Failed to list files: {e}")
                raise
        
        async def download_file(params: Dict) -> Dict:
            """Download a file from Slack"""
            try:
                file_id = params.get("file_id")
                agent_identifier = params.get("agent_color") or params.get("agent_name")
                
                if not file_id:
                    raise ValueError("No file_id provided")
                
                # Get appropriate Slack client
                slack_client = get_slack_client(agent_identifier)
                if not slack_client:
                    raise ValueError("Slack client not available")
                
                result = await slack_client.download_file(file_id)
                return result
            except Exception as e:
                logger.error(f"Failed to download file: {e}")
                raise
        
        async def delete_file(params: Dict) -> Dict:
            """Delete a file from Slack"""
            try:
                file_id = params.get("file_id")
                agent_identifier = params.get("agent_color") or params.get("agent_name")
                
                if not file_id:
                    raise ValueError("No file_id provided")
                
                # Get appropriate Slack client
                slack_client = get_slack_client(agent_identifier)
                if not slack_client:
                    raise ValueError("Slack client not available")
                
                result = await slack_client.delete_file(file_id)
                return result
            except Exception as e:
                logger.error(f"Failed to delete file: {e}")
                raise
        
        async def health_check(params: Dict) -> Dict:
            """Health check endpoint"""
            return {
                "status": "healthy",
                "uptime": "running",
                "version": "2.0.0-consolidated",
                "port": self.http_server.port if self.http_server else "unknown",
                "host": self.http_server.host if self.http_server else "unknown", 
                "default_channel": self.default_channel,
                "config_path": self.config_path,
                "agents": list(self.slack_clients.keys()),
                "agent_configs": {color: config.get("name", f"Agent-{color.title()}") 
                                for color, config in self.agent_configs.items()}
            }
        
        # Register all handlers with HTTP server
        if self.http_server:
            logger.info("Registering HTTP handlers...")
            self.http_server.register_handler("slack.send_message", send_message)
            self.http_server.register_handler("slack.get_messages", get_messages)
            self.http_server.register_handler("slack.get_relevant_messages", get_relevant_messages)
            self.http_server.register_handler("slack.add_reaction", add_reaction)
            self.http_server.register_handler("slack.get_channels", get_channels)
            self.http_server.register_handler("slack.upload_file", upload_file)
            self.http_server.register_handler("slack.list_files", list_files)
            self.http_server.register_handler("slack.download_file", download_file)
            self.http_server.register_handler("slack.delete_file", delete_file)
            self.http_server.register_handler("daemon.health_check", health_check)
            logger.info(f"Registered {len(self.http_server.handlers)} HTTP handlers")
        else:
            raise RuntimeError("HTTP server is required but not initialized")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        config_path = Path(__file__).parent / "slack_config.json"
    else:
        config_path = sys.argv[1]
    
    daemon = SlackDaemon(str(config_path))
    
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted")
    except Exception as e:
        logger.error(f"Daemon failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

