#!/usr/bin/env python3
"""
HTTP REST Client for Slack Daemon
Simple replacement for MCP tools - just makes direct HTTP calls
Auto-detects agent name and prefixes messages appropriately
"""
import json
import requests
import sys
import os
import re
from typing import Optional, Dict, Any

class SlackRESTClient:
    def __init__(self, base_url: str = None):
        if base_url is None:
            # Find running Slack daemon by scanning common ports
            base_url = self._discover_running_daemon()
        
        
        self.base_url = base_url.rstrip("/")
    
    def _discover_running_daemon(self) -> str:
        """
        Discover running Slack daemon by testing common ports
        Scans port range to find an active daemon
        """
        import socket
        from contextlib import closing
        
        # Common port range for Slack daemons
        base_port = 19842
        port_range = 100
        
        for port in range(base_port, base_port + port_range):
            try:
                # Quick socket test to see if port is occupied
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                    sock.settimeout(0.1)
                    if sock.connect_ex(('127.0.0.1', port)) == 0:
                        # Port is occupied, test if it's our daemon
                        test_url = f"http://127.0.0.1:{port}"
                        try:
                            response = requests.get(f"{test_url}/health", timeout=1)
                            if response.status_code == 200:
                                data = response.json()
                                if data.get("success") and "agents" in data.get("result", {}):
                                    return test_url
                        except:
                            continue
            except:
                continue
                
        # Fallback to default port
        return "http://127.0.0.1:19842"
    
    def _detect_agent_color(self) -> str:
        """
        Auto-detect agent color token from various sources
        Priority: ENV_VAR > .agent file > directory patterns > default
        """
        # Check environment variable first
        agent_color = os.environ.get('SLACK_AGENT_COLOR')
        if agent_color and agent_color in ['red', 'blue', 'green', 'black']:
            return agent_color
        
        # Check for simple .agent file in current directory (should contain just the color)
        agent_file = os.path.join(os.getcwd(), '.agent')
        if os.path.exists(agent_file):
            try:
                with open(agent_file, 'r') as f:
                    color = f.read().strip().lower()
                    if color in ['red', 'blue', 'green', 'black']:
                        return color
            except:
                pass
        
        # Check working directory for hints and map to colors
        cwd = os.getcwd().lower()
        if 'cloudshell' in cwd:
            return 'black'
        elif any(env in cwd for env in ['sam', 'development', 'dev']):
            return 'red'
        elif 'mikhail' in cwd:
            return 'blue'
        elif 'knowledge' in cwd:
            return 'green'
        elif any(env in cwd for env in ['slack', 'controller']):
            return 'red'  # Default controller to red
        
        # Default fallback
        return 'red'
    

    
    def send_message(self, text: str, channel: Optional[str] = None, 
                    agent_color: Optional[str] = None, auto_prefix: bool = False) -> Dict[str, Any]:
        """
        Send a message to Slack using color-based agent identification
        
        Args:
            text: Message text
            channel: Optional channel override
            agent_color: Optional agent color override (red, blue, green, black)
            auto_prefix: Whether to add agent prefix (backwards compatibility)
        """
        if not agent_color:
            agent_color = self._detect_agent_color()
            
        if auto_prefix:
            # For backwards compatibility - show display name in prefix
            color_to_name = {
                'red': 'Agent-Sam',
                'blue': 'Agent-Mikhail', 
                'green': 'Agent-Knowledge',
                'black': 'Agent-CloudShell'
            }
            display_name = color_to_name.get(agent_color, f'Agent-{agent_color.title()}')
            text = f"*[{display_name}]:* {text}"
        
        # Send color as agent_color parameter
        data = {"text": text, "agent_color": agent_color}
        if channel:
            data["channel"] = channel
        
        response = requests.post(
            f"{self.base_url}/send_message",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def get_messages(self, limit: int = 50, since_timestamp: Optional[str] = None, 
                    channel: Optional[str] = None, agent_color: Optional[str] = None) -> Dict[str, Any]:
        """Get messages from Slack"""
        if not agent_color:
            agent_color = self._detect_agent_color()
            
        params = {"limit": limit, "agent_color": agent_color}
        if since_timestamp:
            params["since_timestamp"] = since_timestamp
        if channel:
            params["channel"] = channel
        
        response = requests.get(f"{self.base_url}/get_messages", params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def get_relevant_messages(self, agent_color: str, limit: int = 50, 
                             since_timestamp: Optional[str] = None, 
                             channel: Optional[str] = None,
                             exclude_reacted: bool = True) -> Dict[str, Any]:
        """Get messages relevant to a specific agent"""
        params = {"agent_color": agent_color, "limit": limit, "exclude_reacted": str(exclude_reacted).lower()}
        if since_timestamp:
            params["since_timestamp"] = since_timestamp
        if channel:
            params["channel"] = channel
        
        response = requests.get(f"{self.base_url}/get_relevant_messages", params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def get_my_messages(self, agent_color: Optional[str] = None, limit: int = 50, 
                        channel: Optional[str] = None) -> Dict[str, Any]:
        """Get messages from an agent's inbox (more efficient than scanning all messages)"""
        if not agent_color:
            agent_color = self._detect_agent_color()
            
        params = {"agent_color": agent_color, "limit": limit}
        if channel:
            params["channel"] = channel
        
        response = requests.get(f"{self.base_url}/get_my_messages", params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def add_reaction(self, timestamp: str, emoji: str, channel: Optional[str] = None, 
                    agent_color: Optional[str] = None) -> Dict[str, Any]:
        """Add a reaction to a message"""
        if not agent_color:
            agent_color = self._detect_agent_color()
            
        data = {"timestamp": timestamp, "emoji": emoji, "agent_color": agent_color}
        if channel:
            data["channel"] = channel
        
        response = requests.post(
            f"{self.base_url}/add_reaction",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def get_channels(self, agent_color: Optional[str] = None) -> Dict[str, Any]:
        """Get list of channels"""
        if not agent_color:
            agent_color = self._detect_agent_color()
            
        params = {"agent_color": agent_color}
        response = requests.get(f"{self.base_url}/get_channels", params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def health_check(self) -> Dict[str, Any]:
        """Check daemon health"""
        response = requests.get(f"{self.base_url}/health")
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def upload_file(self, file_path: str, comment: str = "", channel: Optional[str] = None, 
                   agent_color: Optional[str] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a file to Slack
        
        Args:
            file_path: Path to the file to upload
            comment: Optional comment for the file
            channel: Optional channel to post the file to
            agent_color: Optional agent color override
            filename: Optional custom filename (defaults to basename of file_path)
        """
        if not agent_color:
            agent_color = self._detect_agent_color()
        
        if not filename:
            filename = os.path.basename(file_path)
        
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")
        
        # Prepare multipart form data
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'application/octet-stream')}
            data = {
                'comment': comment,
                'agent_color': agent_color,
                'filename': filename
            }
            if channel:
                data['channel'] = channel
            
            response = requests.post(
                f"{self.base_url}/upload_file",
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def download_file(self, file_id: str, save_path: str, agent_color: Optional[str] = None) -> Dict[str, Any]:
        """
        Download a file from Slack
        
        Args:
            file_id: Slack file ID to download
            save_path: Local path where to save the file
            agent_color: Optional agent color override
        """
        if not agent_color:
            agent_color = self._detect_agent_color()
        
        params = {
            "file_id": file_id,
            "agent_color": agent_color
        }
        
        response = requests.get(f"{self.base_url}/download_file", params=params)
        
        if response.status_code == 200:
            # Save the file content
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return {"success": True, "message": f"File saved to {save_path}"}
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def list_files(self, limit: int = 100, channel: Optional[str] = None, 
                  agent_color: Optional[str] = None) -> Dict[str, Any]:
        """
        List files in Slack
        
        Args:
            limit: Maximum number of files to return (default: 100)
            channel: Optional channel to filter by
            agent_color: Optional agent color override
        """
        if not agent_color:
            agent_color = self._detect_agent_color()
        
        params = {"limit": limit, "agent_color": agent_color}
        if channel:
            params["channel"] = channel
        
        response = requests.get(f"{self.base_url}/list_files", params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
    
    def delete_file(self, file_id: str, agent_color: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a file from Slack
        
        Args:
            file_id: Slack file ID to delete
            agent_color: Optional agent color override
        """
        if not agent_color:
            agent_color = self._detect_agent_color()
        
        data = {"file_id": file_id, "agent_color": agent_color}
        
        response = requests.post(
            f"{self.base_url}/delete_file",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

# CLI interface for easy command line usage
def show_help():
    """Display comprehensive help text"""
    print("Slack REST Client - HTTP interface to Slack daemon")
    print("=" * 55)
    print()
    print("USAGE:")
    print("  python3 slack_rest_client.py <command> [arguments] [options]")
    print()
    print("COMMANDS:")
    print("  send_message <text> [--prefix] [--agent=NAME]")
    print("      Send a message to Slack")
    print("      --prefix: Add agent prefix (not needed with individual bots)")
    print("      --agent=NAME: Override detected agent name")
    print()
    print("  get_messages [limit]")
    print("      Get recent messages (default limit: 50)")
    print()
    print("  get_relevant_messages [agent_name] [limit] [--include-reacted]")
    print("      Get unread messages relevant to agent (auto-detects agent if not specified)")
    print("      --include-reacted: Include messages the bot has already reacted to")
    print()
    print("  get_my_messages [agent_name] [limit] [--channel=<channel>]")
    print("      Get messages from agent's inbox (more efficient than scanning all messages)")
    print("      Agent inbox is populated automatically when messages mention you")
    print()
    print("  add_reaction <timestamp> <emoji> [channel]")
    print("      Add reaction to message (also marks as read)")
    print("      Example: add_reaction '1234567890.123456' 'thumbsup'")
    print()
    print("  get_channels")
    print("      List available Slack channels")
    print()
    print("  health")
    print("      Check daemon health and connectivity")
    print()
    print("  detect_agent")
    print("      Show detected agent name and detection details")
    print()
    print("  upload_file <file_path> [comment] [--channel=CHANNEL]")
    print("      Upload a file to Slack with optional comment")
    print("      Example: upload_file document.pdf 'Project documentation'")
    print()
    print("  download_file <file_id> <save_path>")
    print("      Download a file from Slack to local path")
    print("      Example: download_file F1234567890 ./downloads/document.pdf")
    print()
    print("  list_files [limit] [--channel=CHANNEL]")
    print("      List files in Slack (default limit: 100)")
    print("      Example: list_files 50 --channel=general")
    print()
    print("  delete_file <file_id>")
    print("      Delete a file from Slack")
    print("      Example: delete_file F1234567890")
    print()
    print("AGENT WORKFLOW:")
    print("  1. Check for relevant messages: get_relevant_messages 10")
    print("  2. Process messages as needed")
    print("  3. Mark as read by reacting: add_reaction 'timestamp' 'eyes'")
    print("  4. Send responses: send_message 'Task completed'")
    print()
    print("AGENT DETECTION:")
    print("  Auto-detects from (in priority order):")
    print("  1. SLACK_AGENT_NAME environment variable")
    print("  2. .agent file in current directory")
    print("  3. agent_*_config.json files")
    print("  4. Directory name patterns")
    print("  5. Defaults to 'Agent-Unknown'")
    print()
    print("EXAMPLES:")
    print("  # Send a message (clean, identified by bot user)")
    print("  python3 slack_rest_client.py send_message 'Task completed successfully'")
    print()
    print("  # Get unread messages for your agent")
    print("  python3 slack_rest_client.py get_relevant_messages 10")
    print()
    print("  # Mark message as read")
    print("  python3 slack_rest_client.py add_reaction '1234567890.123456' 'eyes'")
    print()
    print("  # Check daemon status")
    print("  python3 slack_rest_client.py health")
    print()
    print("  # Upload a file")
    print("  python3 slack_rest_client.py upload_file document.pdf 'Project docs'")
    print()
    print("  # List recent files")
    print("  python3 slack_rest_client.py list_files 20")
    print()
    print("  # Download a file")
    print("  python3 slack_rest_client.py download_file F1234567890 ./downloads/doc.pdf")
    print()
    print("DAEMON ENDPOINTS:")
    print("  Health:      GET  http://127.0.0.1:19842/health")
    print("  Send:        POST http://127.0.0.1:19842/send_message")
    print("  Get:         GET  http://127.0.0.1:19842/get_messages")
    print("  Relevant:    GET  http://127.0.0.1:19842/get_relevant_messages")
    print("  React:       POST http://127.0.0.1:19842/add_reaction")
    print("  Channels:    GET  http://127.0.0.1:19842/get_channels")
    print("  Upload:      POST http://127.0.0.1:19842/upload_file")
    print("  Download:    GET  http://127.0.0.1:19842/download_file")
    print("  List Files:  GET  http://127.0.0.1:19842/list_files")
    print("  Delete File: POST http://127.0.0.1:19842/delete_file")

def main():
    client = SlackRESTClient()
    
    # Check for help flag
    if len(sys.argv) < 2 or any(arg in ['--help', '-h', 'help'] for arg in sys.argv):
        show_help()
        sys.exit(0)
    
    command = sys.argv[1]
    
    try:
        if command == "send_message":
            if len(sys.argv) < 3:
                print("Error: Message text required")
                sys.exit(1)
            
            message = sys.argv[2]
            channel = None
            agent_color = None
            auto_prefix = False
            
            # Parse additional arguments
            for arg in sys.argv[3:]:
                if arg == "--prefix":
                    auto_prefix = True
                elif arg.startswith("--agent="):
                    agent_color = arg.split("=", 1)[1]
                elif arg.startswith("--color="):
                    agent_color = arg.split("=", 1)[1]
                elif not arg.startswith("--"):
                    channel = arg
            
            result = client.send_message(message, channel, agent_color, auto_prefix)
            print(json.dumps(result, indent=2))
        
        elif command == "detect_agent":
            agent_color = client._detect_agent_color()
            color_to_name = {
                'red': 'Agent-Sam',
                'blue': 'Agent-Mikhail', 
                'green': 'Agent-Knowledge',
                'black': 'Agent-CloudShell'
            }
            display_name = color_to_name.get(agent_color, f'Agent-{agent_color.title()}')
            print(f"Detected agent color: {agent_color} ({display_name})")
            print(f"Environment SLACK_AGENT_COLOR: {os.environ.get('SLACK_AGENT_COLOR', 'Not set')}")
            print(f"Current directory: {os.getcwd()}")
            
            # Check .agent file
            agent_file = os.path.join(os.getcwd(), '.agent')
            if os.path.exists(agent_file):
                try:
                    with open(agent_file, 'r') as f:
                        content = f.read().strip()
                        print(f".agent file contains: '{content}'")
                except:
                    print(".agent file exists but couldn't read it")
        
        elif command == "get_messages":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            result = client.get_messages(limit=limit)
            print(json.dumps(result, indent=2))
        
        elif command == "get_relevant_messages":
            # Allow agent color to be optional - will use auto-detected if not provided
            if len(sys.argv) >= 3 and not sys.argv[2].startswith("--") and not sys.argv[2].isdigit():
                agent_color = sys.argv[2]
                start_idx = 3
            else:
                agent_color = client._detect_agent_color()
                start_idx = 2
            
            limit = 50
            exclude_reacted = True
            
            # Parse additional arguments
            for i, arg in enumerate(sys.argv[start_idx:], start_idx):
                if arg == "--include-reacted":
                    exclude_reacted = False
                elif arg.isdigit():
                    limit = int(arg)
            
            result = client.get_relevant_messages(agent_color, limit=limit, exclude_reacted=exclude_reacted)
            print(json.dumps(result, indent=2))
        
        elif command == "get_my_messages":
            # Allow agent_color to be optional - will use auto-detected if not provided
            if len(sys.argv) >= 3 and not sys.argv[2].startswith("--") and not sys.argv[2].isdigit():
                agent_color = sys.argv[2]
                start_idx = 3
            else:
                agent_color = client._detect_agent_color()
                start_idx = 2
            
            limit = 50
            channel = None
            
            # Parse additional arguments
            for i, arg in enumerate(sys.argv[start_idx:], start_idx):
                if arg.startswith("--channel="):
                    channel = arg.split("=", 1)[1]
                elif arg.isdigit():
                    limit = int(arg)
            
            result = client.get_my_messages(agent_color, limit=limit, channel=channel)
            print(json.dumps(result, indent=2))
        
        elif command == "add_reaction":
            if len(sys.argv) < 4:
                print("Error: timestamp and emoji required")
                sys.exit(1)
            
            timestamp = sys.argv[2]
            emoji = sys.argv[3]
            channel = sys.argv[4] if len(sys.argv) > 4 else None
            result = client.add_reaction(timestamp, emoji, channel)
            print(json.dumps(result, indent=2))
        
        elif command == "get_channels":
            result = client.get_channels()
            print(json.dumps(result, indent=2))
        
        elif command == "health":
            result = client.health_check()
            print(json.dumps(result, indent=2))
        
        elif command == "upload_file":
            if len(sys.argv) < 3:
                print("Error: file_path required")
                sys.exit(1)
            
            file_path = sys.argv[2]
            comment = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else ""
            channel = None
            
            # Parse additional arguments
            for arg in sys.argv[3:]:
                if arg.startswith("--channel="):
                    channel = arg.split("=", 1)[1]
            
            result = client.upload_file(file_path, comment, channel)
            print(json.dumps(result, indent=2))
        
        elif command == "download_file":
            if len(sys.argv) < 4:
                print("Error: file_id and save_path required")
                sys.exit(1)
            
            file_id = sys.argv[2]
            save_path = sys.argv[3]
            result = client.download_file(file_id, save_path)
            print(json.dumps(result, indent=2))
        
        elif command == "list_files":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 100
            channel = None
            
            # Parse additional arguments
            for arg in sys.argv[2:]:
                if arg.startswith("--channel="):
                    channel = arg.split("=", 1)[1]
            
            result = client.list_files(limit=limit, channel=channel)
            print(json.dumps(result, indent=2))
        
        elif command == "delete_file":
            if len(sys.argv) < 3:
                print("Error: file_id required")
                sys.exit(1)
            
            file_id = sys.argv[2]
            result = client.delete_file(file_id)
            print(json.dumps(result, indent=2))
        
        elif command in ["help", "--help", "-h"]:
            show_help()
        
        else:
            print(f"Unknown command: {command}")
            print("Use 'python3 slack_rest_client.py --help' for usage information.")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()