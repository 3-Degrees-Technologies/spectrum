#!/usr/bin/env python3
"""
Consolidated Slack Bridge - Single file daemon
Combines all daemon functionality with color-based agent identification
"""

# VERSION TRACKING
PUENTE_VERSION = "2.2.2-timestamp-precision-fix"
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

# Logging will be configured later when config is loaded
logger = logging.getLogger(__name__)

def convert_markdown_to_slack(text: str) -> str:
    """
    Convert markdown formatting to Slack formatting
    **bold** -> *bold*
    *italic* -> _italic_ 
    `code` -> ```code```
    ```code block``` -> ```code block``` (unchanged)
    """
    import re
    
    # First, temporarily replace **bold** with a placeholder to avoid conflicts
    # Step 1: **bold** -> BOLD_PLACEHOLDER
    bold_patterns = []
    def store_bold(match):
        bold_patterns.append(match.group(1))
        return f"__BOLD_PLACEHOLDER_{len(bold_patterns)-1}__"
    
    text = re.sub(r'\*\*(.+?)\*\*', store_bold, text)
    
    # Step 2: *italic* -> _italic_ (now safe from **bold** interference)
    text = re.sub(r'\*([^*]+?)\*', r'_\1_', text)
    
    # Step 3: `code` -> ```code``` (single backticks to triple backticks)
    text = re.sub(r'`([^`]+?)`', r'```\1```', text)
    
    # Step 4: Restore **bold** as *bold*
    for i, bold_content in enumerate(bold_patterns):
        text = text.replace(f"__BOLD_PLACEHOLDER_{i}__", f"*{bold_content}*")
    
    return text

def convert_slack_to_markdown(text: str) -> str:
    """
    Convert Slack formatting to markdown formatting (reverse conversion)
    *bold* -> **bold**
    _italic_ -> *italic*
    `code` -> `code` (unchanged)
    """
    import re
    
    # Convert *bold* to **bold**
    text = re.sub(r'\*([^*]+?)\*', r'**\1**', text)
    
    # Convert _italic_ to *italic*
    text = re.sub(r'_([^_]+?)_', r'*\1*', text)
    
    return text

def replace_agent_mentions(text: str, agent_configs: Dict) -> str:
    """
    Replace @agent-name and @agent-color mentions with proper Slack user ID mentions
    Example: @agent-sam -> <@U096VLDAHJ5>
    Example: @Agent Sam -> <@U096VLDAHJ5>
    Example: @Agent-Red -> <@U096VLDAHJ5>
    Example: @Agent Red -> <@U096VLDAHJ5>
    Case-insensitive matching with flexible spacing and hyphenation
    """
    import re
    
    for color, config in agent_configs.items():
        name = config.get("name", "")
        user_id = config.get("bot_user_id", "")
        
        if user_id:
            # Pattern 1: Match by agent name (if available)
            if name:
                flexible_name = re.escape(name).replace(r'\-', r'[\s\-]?')
                pattern = f"@{flexible_name}"
                replacement = f"<@{user_id}>"
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
            # Pattern 2: Match by agent color (@Agent-Red, @Agent Red, etc.)
            flexible_color = re.escape(f"agent-{color}").replace(r'\-', r'[\s\-]?')
            pattern = f"@{flexible_color}"
            replacement = f"<@{user_id}>"
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def filter_relevant_messages_for_agent(messages, agent_identifier, exclude_reacted=True, bot_user_id=None, friendly_agent_name=None, config_bot_name=None):
    """
    Filter messages for relevance to a specific agent (color or name)
    Implements 6-pattern detection:
      a) Friendly agent name with "Agent-" prefix (e.g., "Agent-Skinner")
      b) Friendly agent name without prefix (e.g., "Skinner")
      c) Slack bot user ID (e.g., <@U123456>)
      d) Color-based agent name with "Agent-" prefix (e.g., "Agent-green")
      e) Color mention (e.g., "@green")
      f) Config bot name (e.g., "agent-abc")
    """
    relevant = []
    
    logger.info(f"🔍 FILTERING: Checking {len(messages)} messages for agent '{agent_identifier}' (bot_user_id: {bot_user_id}, friendly_name: {friendly_agent_name})")
    
    # Keywords that indicate team-wide relevance
    team_keywords = [
        "@here", "@channel", "@everyone",
        "all agents", "team meeting", "system alert", 
        "critical", "emergency", "deployment", "outage",
        "maintenance", "daemon restart"
    ]
    
    # Build detection patterns (case-insensitive)
    detection_patterns = []
    
    # Pattern a) & b) Friendly agent name (with and without "Agent-" prefix)
    if friendly_agent_name:
        detection_patterns.append(f"agent-{friendly_agent_name.lower()}")  # "Agent-Skinner"
        detection_patterns.append(f"@agent-{friendly_agent_name.lower()}")
        detection_patterns.append(friendly_agent_name.lower())  # "Skinner"
        detection_patterns.append(f"@{friendly_agent_name.lower()}")
    
    # Pattern d) & e) Color-based agent name (with and without "Agent-" prefix)
    detection_patterns.append(f"agent-{agent_identifier.lower()}")  # "Agent-red"
    detection_patterns.append(f"@agent-{agent_identifier.lower()}")
    detection_patterns.append(f"@{agent_identifier.lower()}")  # "@red"
    
    # Pattern f) Config bot name
    if config_bot_name:
        detection_patterns.append(config_bot_name.lower())
        detection_patterns.append(f"@{config_bot_name.lower()}")
    
    # Additional flexible patterns for color agents
    if agent_identifier.lower() in ['red', 'blue', 'green', 'black']:
        detection_patterns.extend([
            f"@agent {agent_identifier.lower()}",  # "@agent red"
            f"@agent{agent_identifier.lower()}",   # "@agentred"
            f"[{agent_identifier.lower()}]",       # "[red]"
            f"{agent_identifier.lower()}:"         # "red:"
        ])
    
    logger.info(f"🔍 FILTERING: Detection patterns: {detection_patterns}")
    
    # Pattern c) Slack user ID mention (preferred)
    user_id_pattern = f"<@{bot_user_id}>" if bot_user_id else None
    logger.info(f"🔍 FILTERING: User ID pattern: {user_id_pattern}")
    
    for msg in messages:
        text = msg.get("text", "")
        text_lower = text.lower()
        user_id = msg.get("user_id", "")
        
        logger.info(f"🔍 FILTERING: Checking message: '{text}' from user {user_id}")
        
        # Skip agent's own messages
        if bot_user_id and user_id == bot_user_id:
            logger.info(f"🔍 FILTERING: ❌ Skipping own message")
            continue
        
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
                logger.info(f"🔍 FILTERING: ❌ Agent already reacted to message, skipping")
                continue
        
        # Check for team-wide alerts first
        team_match = any(keyword.lower() in text_lower for keyword in team_keywords)
        if team_match:
            logger.info(f"🔍 FILTERING: ✅ Team-wide match: {text[:50]}...")
            relevant.append(msg)
            continue
            
        # Check for proper Slack user ID mentions first (Pattern c - preferred)
        user_id_match = user_id_pattern and user_id_pattern in text
        if user_id_match:
            logger.info(f"🔍 FILTERING: ✅ User ID match: {text[:50]}...")
            relevant.append(msg)
            continue
            
        # Check all text-based detection patterns
        message_matched = False
        for pattern in detection_patterns:
            if pattern in text_lower:
                logger.info(f"🔍 FILTERING: ✅ Pattern match '{pattern}': {text[:50]}...")
                # Validate that this isn't part of another word/agent name
                pattern_pos = text_lower.find(pattern)
                if pattern_pos >= 0:
                    # Check what comes after the pattern
                    after_pattern_pos = pattern_pos + len(pattern)
                    if after_pattern_pos < len(text_lower):
                        next_char = text_lower[after_pattern_pos]
                        # If followed by alphanumeric/hyphen, might be part of another name
                        if pattern.startswith('@') and (next_char.isalnum() or next_char == '-'):
                            logger.info(f"🔍 FILTERING: False positive for pattern '{pattern}', next char: '{next_char}'")
                            continue  # Skip this pattern
                    message_matched = True
                    break
        
        if message_matched:
            relevant.append(msg)
        else:
            logger.info(f"🔍 FILTERING: ❌ No match: {text[:50]}...")
            
    logger.info(f"🔍 FILTERING: Found {len(relevant)} relevant messages out of {len(messages)} total")
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
        self.session: Optional[ClientSession] = None
        
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
                    if self.session:
                        async with self.session.post(url, headers=headers, data=data) as response:
                            result = await response.json()
                    else:
                        raise Exception("Session not initialized")
                else:
                    # For regular API calls - check if endpoint requires form data
                    if endpoint == "files.getUploadURLExternal":
                        # This endpoint expects form data, not JSON
                        headers.pop("Content-Type", None)  # Let aiohttp set the correct content-type
                        if self.session:
                            async with self.session.post(url, headers=headers, data=data) as response:
                                result = await response.json()
                        else:
                            raise Exception("Session not initialized")
                    else:
                        # Regular JSON API calls (including files.completeUploadExternal)
                        if self.session:
                            async with self.session.post(url, headers=headers, json=data) as response:
                                result = await response.json()
                        else:
                            raise Exception("Session not initialized")
            else:
                if self.session:
                    async with self.session.get(url, headers=headers, params=data) as response:
                        result = await response.json()
                else:
                    raise Exception("Session not initialized")
            
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
    
    async def upload_file(self, file_data: bytes, filename: str, comment: str = "", channel: Optional[str] = None) -> Dict:
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
        if self.session:
            async with self.session.post(upload_url, data=file_data) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"File upload failed: {response.status} - {response_text}")
                    raise ValueError(f"Failed to upload file: {response.status}")
        else:
            raise Exception("Session not initialized")
        
        logger.info("File uploaded successfully, completing...")
        
        # Step 3: Complete the upload
        complete_params: Dict[str, Any] = {
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
    
    async def list_files(self, channel: Optional[str] = None, limit: int = 100) -> Dict:
        """List files from Slack"""
        params: Dict[str, Any] = {"count": limit}
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
        if not self.app:
            raise RuntimeError("App not initialized")
            
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
        
        # Agent registration endpoints
        self.app.router.add_post('/register_agent', self._handle_register_agent)
        self.app.router.add_post('/unregister_agent', self._handle_unregister_agent)
        self.app.router.add_get('/list_agents', self._handle_list_agents)
        
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
                try:
                    field_name = getattr(field, 'name', None)
                    if field_name == 'file':
                        file_data = await field.read()  # type: ignore
                        filename = getattr(field, 'filename', None)
                    elif field_name:
                        params[field_name] = await field.text()  # type: ignore
                except Exception as e:
                    logger.warning(f"Error processing multipart field: {e}")
                    continue
            
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

    async def _handle_register_agent(self, request: Request) -> Response:
        """Handle agent registration POST request"""
        try:
            if request.content_type == 'application/json':
                params = await request.json()
            else:
                params = dict(await request.post())
            
            if "daemon.register_agent" in self.handlers:
                result = await self.handlers["daemon.register_agent"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in register_agent: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_unregister_agent(self, request: Request) -> Response:
        """Handle agent unregistration POST request"""
        try:
            if request.content_type == 'application/json':
                params = await request.json()
            else:
                params = dict(await request.post())
            
            if "daemon.unregister_agent" in self.handlers:
                result = await self.handlers["daemon.unregister_agent"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in unregister_agent: {e}")
            return json_response({"error": str(e)}, status=500)
    
    async def _handle_list_agents(self, request: Request) -> Response:
        """Handle list agents GET request"""
        try:
            params = {}
            
            if "daemon.list_agents" in self.handlers:
                result = await self.handlers["daemon.list_agents"](params)
                return json_response({"success": True, "result": result})
            else:
                return json_response({"error": "Handler not registered"}, status=500)
                
        except Exception as e:
            logger.error(f"Error in list_agents: {e}")
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
        
        # Agent registration tracking - maps color to OpenCode port and per-agent message timestamp
        self.registered_agents = {}  # {"red": {"port": 44817, "last_seen": timestamp, "last_message_timestamp": "123456.789"}}
        
        # Message monitoring for auto-notifications
        self.monitoring_task = None
        
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
        if self.config:
            compat_mapping = self.config.get("backwards_compatibility", {}).get("agent_name_to_color", {})
            return compat_mapping.get(identifier)
        return None
    
    def get_agent_name_by_color(self, color: str) -> str:
        """Get agent display name by color"""
        agent_config = self.agent_configs.get(color, {})
        return agent_config.get("name", f"Agent-{color.title()}")
    
    async def start(self):
        """Start the daemon"""
        await self.load_config()
        
        # Log version immediately at startup
        logger.info(f"🚀 PUENTE STARTING: Version {PUENTE_VERSION}")
        
        # Initialize Slack clients for each color-based agent
        if not self.config:
            raise RuntimeError("Configuration not loaded")
            
        rate_config = self.config["rate_limiting"]
        
        # Set default channel
        self.default_channel = self.config.get("daemon", {}).get("default_channel")
        
        # Create Slack clients for each color-based agent
        for color, agent_config in self.agent_configs.items():
            bot_token = agent_config.get("bot_token")
            
            if bot_token:
                self.slack_clients[color] = SlackAPIClient(
                    bot_token=bot_token,
                    app_token="",  # Not needed for REST API approach
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
        
        # Start message monitoring for auto-notifications
        self.monitoring_task = asyncio.create_task(self._monitor_and_notify())
        
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
        
        # Stop monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
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
    
    async def _monitor_and_notify(self):
        """Monitor for new messages and automatically notify registered agents"""
        logger.info(f"📡 MONITORING STARTING: Version {PUENTE_VERSION} - Starting message monitoring for auto-notifications...")
        
        while self.is_running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                if not self.registered_agents:
                    continue
                
                # Get recent messages - each agent tracks its own last message timestamp
                for agent_color, agent_info in self.registered_agents.items():
                    logger.info(f"📬 MONITORING: Checking messages for {agent_color} agent (port {agent_info.get('opencode_port')})")
                    
                    if agent_color not in self.agent_configs:
                        logger.warning(f"📬 MONITORING: {agent_color} not in agent_configs")
                        continue
                        
                    # Get the Slack client for this agent's color
                    if agent_color not in self.slack_clients:
                        logger.warning(f"📬 MONITORING: {agent_color} not in slack_clients")
                        continue
                        
                    client = self.slack_clients[agent_color]
                    agent_config = self.agent_configs[agent_color]
                    bot_user_id = agent_config.get("bot_user_id")
                    
                    # Use agent-specific last message timestamp
                    agent_last_timestamp = agent_info.get("last_message_timestamp")
                    
                    logger.info(f"📬 MONITORING: {agent_color} last timestamp: {agent_last_timestamp}")
                    
                    try:
                        messages = await client.get_messages(
                            channel=self.default_channel,
                            limit=10,
                            since_timestamp=agent_last_timestamp
                        )
                        
                        logger.info(f"📬 MONITORING: Found {len(messages)} new messages for {agent_color}")
                        
                        if messages:
                            # Filter for messages relevant to this specific agent FIRST
                            relevant_messages = filter_relevant_messages_for_agent(
                                messages, agent_color, True, bot_user_id
                            )
                            
                            logger.info(f"📬 MONITORING: Found {len(relevant_messages)} relevant messages for {agent_color}")
                            
                            # Send batch notification for relevant messages
                            if relevant_messages:
                                logger.info(f"📬 MONITORING: Sending batch notification for {len(relevant_messages)} messages")
                                await self._notify_agent_batch(agent_color, agent_info["opencode_port"], relevant_messages)
                            
                            # Update timestamp ONLY AFTER processing - use latest timestamp from ALL messages
                            latest_ts = max(float(msg.get("timestamp", 0)) for msg in messages)
                            if not agent_last_timestamp or latest_ts > float(agent_last_timestamp or "0"):
                                self.registered_agents[agent_color]["last_message_timestamp"] = f"{latest_ts:.6f}"
                                logger.info(f"📬 MONITORING: Updated {agent_color} timestamp to {latest_ts:.6f}")
                                
                    except Exception as e:
                        logger.error(f"Error monitoring messages for {agent_color}: {e}")
                        
            except Exception as e:
                logger.error(f"Error in message monitoring: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _notify_agent(self, agent_color: str, opencode_port: int, message: Dict):
        """Send notification to a specific agent's OpenCode instance using correct OpenCode API"""
        try:
            import aiohttp
            
            user_name = message.get("user_name", "Unknown")
            message_text = message.get("text", "")
            
            logger.info(f"🔔 ATTEMPTING NOTIFICATION: Sending to {agent_color} agent on port {opencode_port}")
            logger.info(f"🔔 MESSAGE FROM: {user_name}")
            logger.info(f"🔔 MESSAGE TEXT: {message_text[:100]}...")
            
            # Clean message text to prevent CRLF issues
            clean_message_text = message_text.replace('\r\n', '\n').replace('\r', '\n').strip()
            
            # Create a prompt message about the new Slack message - this will be visible to the AI agent
            notification_prompt = f"🔔 SLACK NOTIFICATION: New message from {user_name}: \"{clean_message_text}\""
            
            async with aiohttp.ClientSession() as session:
                # Method 1: Try appending text to prompt (works reliably)
                append_url = f"http://127.0.0.1:{opencode_port}/tui/append-prompt"
                append_payload = {"text": notification_prompt}
                
                logger.info(f"🔔 APPEND URL: {append_url}")
                logger.info(f"🔔 APPEND PAYLOAD: {append_payload}")
                
                async with session.post(append_url, json=append_payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status == 200:
                        logger.info(f"✅ APPEND SUCCESS: {agent_color} agent on port {opencode_port}: notification text appended")
                        
                        # Method 2: Show toast notification (backup method that works reliably)
                        toast_url = f"http://127.0.0.1:{opencode_port}/tui/show-toast"
                        toast_payload = {
                            "title": f"Slack Notification from {user_name}",
                            "message": clean_message_text[:100],
                            "variant": "info"
                        }
                        
                        logger.info(f"🔔 TOAST URL: {toast_url}")
                        logger.info(f"🔔 TOAST PAYLOAD: {toast_payload}")
                        
                        async with session.post(toast_url, json=toast_payload, headers={"Content-Type": "application/json"}) as response:
                            if response.status == 200:
                                logger.info(f"✅ TOAST SUCCESS: {agent_color} agent on port {opencode_port}: toast notification shown")
                        logger.info(f"📬 NOTIFICATION DELIVERED: Message from {user_name} has been auto-submitted for immediate processing")
                        return
                    else:
                        response_text = await response.text()
                        logger.warning(f"⚠️ TUI SUBMIT FAILED: {agent_color} agent: HTTP {response.status} - {response_text}")
                
                # Method 2: Fallback to show-toast notification (non-intrusive)
                toast_url = f"http://127.0.0.1:{opencode_port}/tui/show-toast"
                toast_payload = {
                    "title": f"Slack Message from {user_name}",
                    "message": message_text[:100] + ("..." if len(message_text) > 100 else ""),
                    "variant": "info"
                }
                
                logger.info(f"🔔 FALLBACK: Trying toast notification")
                logger.info(f"🔔 TOAST URL: {toast_url}")
                logger.info(f"🔔 TOAST PAYLOAD: {toast_payload}")
                
                async with session.post(toast_url, json=toast_payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status == 200:
                        logger.info(f"✅ TOAST SUCCESS: {agent_color} agent on port {opencode_port}: toast shown for message from {user_name}")
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ TOAST FAILED: {agent_color} agent: HTTP {response.status} - {response_text}")
                        
        except Exception as e:
            logger.error(f"💥 NOTIFICATION ERROR: Error notifying {agent_color} agent: {e}")
            import traceback
            logger.error(f"💥 NOTIFICATION TRACEBACK: {traceback.format_exc()}")
    
    async def _notify_agent_batch(self, agent_color: str, opencode_port: int, messages: List[Dict]):
        """Send a single batch notification about multiple new messages"""
        try:
            import aiohttp
            
            message_count = len(messages)
            if message_count == 0:
                return
                
            logger.info(f"🔔 BATCH NOTIFICATION V{PUENTE_VERSION}: Sending summary of {message_count} messages to {agent_color} agent on port {opencode_port}")
            
            # Create simple notification prompt for append
            if message_count == 1:
                msg = messages[0]
                user_name = msg.get("user_name", "Unknown")
                notification_prompt = f"🔔 You have a new Slack message from {user_name}"
            else:
                # Get unique senders
                senders = list(set(msg.get("user_name", "Unknown") for msg in messages))
                if len(senders) == 1:
                    sender_summary = f"from {senders[0]}"
                elif len(senders) == 2:
                    sender_summary = f"from {senders[0]} and {senders[1]}"
                else:
                    sender_summary = f"from {senders[0]} and {len(senders)-1} others"
                
                notification_prompt = f"🔔 You have {message_count} new Slack messages {sender_summary}"
            
            async with aiohttp.ClientSession() as session:
                # Step 1: Append the message content to the prompt
                append_url = f"http://127.0.0.1:{opencode_port}/tui/append-prompt"
                append_payload = {"text": notification_prompt}
                
                logger.info(f"🔔 STEP 1 - APPEND URL: {append_url}")
                logger.info(f"🔔 STEP 1 - APPEND PAYLOAD: {append_payload}")
                
                async with session.post(append_url, json=append_payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status == 200 and notification_prompt and notification_prompt.strip():
                        logger.info(f"✅ STEP 1 SUCCESS: Message content appended to {agent_color} agent prompt")
                        logger.info(f"✅ APPENDED CONTENT: {notification_prompt[:200]}...")
                        
                        # Step 2: Submit the prompt for processing (no additional text needed)
                        submit_url = f"http://127.0.0.1:{opencode_port}/tui/submit-prompt"
                        submit_payload = {}  # No text parameter - just submit what's in the prompt
                        
                        logger.info(f"🔔 STEP 2 - SUBMIT URL: {submit_url}")
                        logger.info(f"🔔 STEP 2 - SUBMIT PAYLOAD: {submit_payload}")
                        
                        async with session.post(submit_url, json=submit_payload, headers={"Content-Type": "application/json"}) as submit_response:
                            if submit_response.status == 200:
                                logger.info(f"✅ STEP 2 SUCCESS: Prompt submitted for {agent_color} agent")
                                logger.info(f"✅ BATCH NOTIFICATION SUCCESS: {agent_color} agent notified of {message_count} messages")
                                return
                            else:
                                submit_response_text = await submit_response.text()
                                logger.warning(f"⚠️ STEP 2 FAILED: Submit failed for {agent_color} agent: HTTP {submit_response.status} - {submit_response_text}")
                    else:
                        response_text = await response.text()
                        logger.warning(f"⚠️ STEP 1 FAILED: Append failed for {agent_color} agent: HTTP {response.status} - {response_text}")
                        logger.warning(f"⚠️ NOTIFICATION CONTENT: '{notification_prompt}'")
                
                # Fallback to toast
                toast_url = f"http://127.0.0.1:{opencode_port}/tui/show-toast"
                toast_payload = {
                    "title": f"{message_count} New Slack Messages",
                    "message": f"You have {message_count} new messages. Use get_relevant_messages to read them.",
                    "variant": "info"
                }
                
                async with session.post(toast_url, json=toast_payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status == 200:
                        logger.info(f"✅ BATCH TOAST SUCCESS: {agent_color} agent notified via toast of {message_count} messages")
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ BATCH TOAST FAILED: {agent_color} agent: HTTP {response.status} - {response_text}")
                        
        except Exception as e:
            logger.error(f"💥 BATCH NOTIFICATION ERROR: Error sending batch notification to {agent_color} agent: {e}")
            import traceback
            logger.error(f"💥 BATCH NOTIFICATION TRACEBACK: {traceback.format_exc()}")
    
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
                
                # Replace literal '\n' text (backslash followed by 'n') with actual newline characters
                # This handles cases where text contains the two-character sequence "\n" rather than an actual newline
                text = text.replace('\\n', '\n')

                if text != original_text:
                    logger.info(f"Replaced mentions in message: {original_text[:50]}... -> {text[:50]}...")
                
                # Convert markdown formatting to Slack formatting
                markdown_converted_text = text
                text = convert_markdown_to_slack(text)
                
                if text != markdown_converted_text:
                    logger.info(f"Converted markdown formatting: {markdown_converted_text[:50]}... -> {text[:50]}...")
                
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
            
            # Use per-agent timestamp tracking if agent is registered
            if color and color in self.registered_agents:
                agent_since_timestamp = self.registered_agents[color].get("last_message_timestamp")
                if agent_since_timestamp and not since_timestamp:
                    since_timestamp = agent_since_timestamp
                    logger.info(f"Using per-agent timestamp for {color}: {since_timestamp}")
            
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
            
            # NOTE: Don't update timestamp here - only monitoring loop should update it
            # to avoid breaking auto-notifications
            
            # Limit to requested amount
            relevant_messages = relevant_messages[:limit]
            
            return {
                "messages": relevant_messages,
                "agent_identifier": agent_identifier,
                "agent_color": color,
                "total_filtered": len(relevant_messages),
                "searched_total": len(messages),
                "exclude_reacted": exclude_reacted,
                "bot_user_id": bot_user_id,
                "since_timestamp": since_timestamp
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
                
                # Apply the same transformations as send_message for the comment
                if comment:
                    # Replace @agent-name mentions with proper Slack user IDs
                    original_comment = comment
                    comment = replace_agent_mentions(comment, self.agent_configs)
                    
                    if comment != original_comment:
                        logger.info(f"Replaced mentions in file comment: {original_comment[:50]}... -> {comment[:50]}...")
                    
                    # Convert markdown formatting to Slack formatting
                    markdown_converted_comment = comment
                    comment = convert_markdown_to_slack(comment)
                    
                    if comment != markdown_converted_comment:
                        logger.info(f"Converted markdown in file comment: {markdown_converted_comment[:50]}... -> {comment[:50]}...")
                
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
                                for color, config in self.agent_configs.items()},
                "registered_agents": self.registered_agents
            }

        async def register_agent(params: Dict) -> Dict:
            """Register an agent for OpenCode notifications"""
            try:
                agent_color = params.get("agent_color")
                opencode_port = params.get("opencode_port")
                
                if not agent_color:
                    raise ValueError("agent_color parameter is required")
                if not opencode_port:
                    raise ValueError("opencode_port parameter is required")
                
                # Validate that this agent color exists in our configuration
                if agent_color not in self.agent_configs:
                    raise ValueError(f"Unknown agent color: {agent_color}. Available: {list(self.agent_configs.keys())}")
                
                # Initialize per-agent tracking
                # Set initial timestamp to 5 seconds ago to catch immediate messages
                initial_timestamp = time.time() - 5.0
                self.registered_agents[agent_color] = {
                    "opencode_port": int(opencode_port),
                    "last_seen": time.time(),
                    "last_message_timestamp": f"{initial_timestamp:.6f}"  # Format to 6 decimal places for Slack compatibility
                }
                
                agent_name = self.get_agent_name_by_color(agent_color)
                logger.info(f"🟢 AGENT REGISTRATION: {agent_name} (color: {agent_color}) registered on OpenCode port {opencode_port}")
                logger.info(f"🟢 TIMESTAMP INIT: Set initial timestamp to {initial_timestamp} (5 seconds ago)")
                logger.info(f"🟢 REGISTERED AGENTS COUNT: {len(self.registered_agents)}")
                logger.info(f"🟢 ALL REGISTERED AGENTS: {list(self.registered_agents.keys())}")
                
                return {
                    "success": True,
                    "agent_color": agent_color,
                    "agent_name": agent_name,
                    "opencode_port": opencode_port,
                    "message": f"Agent {agent_name} registered successfully"
                }
                
            except Exception as e:
                logger.error(f"Failed to register agent: {e}")
                raise

        async def unregister_agent(params: Dict) -> Dict:
            """Unregister an agent from OpenCode notifications"""
            try:
                agent_color = params.get("agent_color")
                
                if not agent_color:
                    raise ValueError("agent_color parameter is required")
                
                if agent_color in self.registered_agents:
                    del self.registered_agents[agent_color]
                    agent_name = self.get_agent_name_by_color(agent_color)
                    logger.info(f"Unregistered {agent_name} (color: {agent_color})")
                    
                    return {
                        "success": True,
                        "agent_color": agent_color,
                        "agent_name": agent_name,
                        "message": f"Agent {agent_name} unregistered successfully"
                    }
                else:
                    return {
                        "success": False,
                        "agent_color": agent_color,
                        "message": f"Agent {agent_color} was not registered"
                    }
                    
            except Exception as e:
                logger.error(f"Failed to unregister agent: {e}")
                raise

        async def list_agents(params: Dict) -> Dict:
            """List all registered agents"""
            try:
                agents = {}
                for color, info in self.registered_agents.items():
                    agent_name = self.get_agent_name_by_color(color)
                    agents[color] = {
                        "name": agent_name,
                        "opencode_port": info["opencode_port"],
                        "last_seen": info["last_seen"],
                        "last_message_timestamp": info["last_message_timestamp"]
                    }
                
                return {
                    "success": True,
                    "registered_agents": agents,
                    "total_count": len(agents)
                }
                
            except Exception as e:
                logger.error(f"Failed to list agents: {e}")
                raise
        
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
            self.http_server.register_handler("daemon.register_agent", register_agent)
            self.http_server.register_handler("daemon.unregister_agent", unregister_agent)
            self.http_server.register_handler("daemon.list_agents", list_agents)
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

