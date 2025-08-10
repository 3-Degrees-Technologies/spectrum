#!/usr/bin/env python3
"""
Slack Config Generator
Generates a complete slack_config.json from tokens and agent-names configuration files
Fetches bot_user_id and bot_id from Slack API automatically
"""
import json
import os
import sys
import requests
from pathlib import Path
from typing import Dict, Any, Optional

def parse_env_file(env_path: str) -> Dict[str, str]:
    """Parse .env file format and return key-value pairs"""
    env_vars = {}
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=value format
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes from value if present
                value = value.strip('"\'')
                env_vars[key.strip()] = value
    
    return env_vars

def get_bot_info_from_slack(bot_token: str) -> Dict[str, str]:
    """
    Fetch bot_user_id and bot_id from Slack API using bot token
    
    Args:
        bot_token: Slack bot token (xoxb-...)
        
    Returns:
        Dictionary with bot_user_id and bot_id, or empty strings if failed
    """
    try:
        # Call auth.test to get bot info
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return {
                    "bot_user_id": data.get("user_id", ""),
                    "bot_id": data.get("bot_id", "")
                }
            else:
                print(f"Slack API error: {data.get('error', 'Unknown error')}")
        else:
            print(f"HTTP error: {response.status_code}")
            
    except Exception as e:
        print(f"Failed to fetch bot info: {e}")
    
    return {"bot_user_id": "", "bot_id": ""}

def generate_slack_config(tokens_dir: str = "tokens", output_file: str = "slack_config.json") -> Dict[str, Any]:
    """
    Generate slack_config.json from tokens directory files
    
    Args:
        tokens_dir: Directory containing agent-names.json and tokens.env
        output_file: Output filename for generated config
        
    Returns:
        Generated configuration dictionary
    """
    tokens_path = Path(tokens_dir)
    
    # Load agent names configuration
    agent_names_file = tokens_path / "agent-names.json"
    if not agent_names_file.exists():
        raise FileNotFoundError(f"Missing {agent_names_file}")
    
    with open(agent_names_file, 'r') as f:
        agent_names = json.load(f)
    
    # Load tokens environment file
    tokens_env_file = tokens_path / "tokens.env"
    if not tokens_env_file.exists():
        raise FileNotFoundError(f"Missing {tokens_env_file}")
    
    env_vars = parse_env_file(str(tokens_env_file))
    
    # Map environment variable names to colors
    token_mapping = {
        'RED_TOKEN': 'red',
        'BLUE_TOKEN': 'blue', 
        'GREEN_TOKEN': 'green',
        'BLACK_TOKEN': 'black'
    }
    
    # Color to hex code mapping
    color_hex = {
        'red': '#e74c3c',
        'blue': '#3498db', 
        'green': '#27ae60',
        'black': '#2c3e50'
    }
    
    # Generate base configuration structure
    config = {
        "daemon": {
            "host": "127.0.0.1",
            "enabled": True,
            "default_channel": env_vars.get("SLACK_CHANNEL_ID", "C094N3NKUR0")
        },
        "rate_limiting": {
            "messages_per_minute": 60,
            "api_calls_per_minute": 100
        },
        "logging": {
            "level": "INFO",
            "file": "/tmp/slack_daemon.log"
        },
        "agents": {}
    }
    
    # Generate agent configurations
    for token_env, color in token_mapping.items():
        if token_env not in env_vars:
            print(f"Warning: Missing token {token_env}")
            continue
            
        agent_info = agent_names.get("agent_names", {}).get(color, {})
        if not agent_info:
            print(f"Warning: Missing agent info for color {color}")
            continue
        
        # Extract display name and convert to lowercase for 'name' field
        display_name = agent_info.get("display_name", f"Agent-{color.title()}")
        agent_name = display_name.lower().replace("agent-", "agent-")
        
        # Fetch bot info from Slack API
        print(f"🔍 Fetching bot info for {display_name}...")
        bot_info = get_bot_info_from_slack(env_vars[token_env])
        
        config["agents"][color] = {
            "name": agent_name,
            "bot_token": env_vars[token_env],
            "bot_user_id": bot_info["bot_user_id"],
            "bot_id": bot_info["bot_id"],
            "color": color_hex[color],
            "default_channel": config["daemon"]["default_channel"]
        }
    
    # Write generated configuration
    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Generated {output_file}")
    print(f"📝 Configuration includes {len(config['agents'])} agents")
    
    # Check if any bot IDs are missing
    missing_ids = []
    for color, agent in config["agents"].items():
        if not agent["bot_user_id"] or not agent["bot_id"]:
            missing_ids.append(color)
    
    if missing_ids:
        print(f"⚠️  Warning: Missing bot IDs for: {', '.join(missing_ids)}")
        print("   Check token permissions or network connectivity")
    else:
        print("✅ All bot IDs fetched successfully")
    
    return config

def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate slack_config.json from token files")
    parser.add_argument("--tokens-dir", default="tokens", 
                       help="Directory containing token files (default: tokens)")
    parser.add_argument("--output", default="slack_config.json",
                       help="Output file name (default: slack_config.json)")
    parser.add_argument("--backup", action="store_true", 
                       help="Backup existing config file before overwriting")
    
    args = parser.parse_args()
    
    try:
        # Backup existing config if requested
        if args.backup and os.path.exists(args.output):
            backup_name = f"{args.output}.backup"
            os.rename(args.output, backup_name)
            print(f"📁 Backed up existing config to {backup_name}")
        
        # Generate new configuration
        config = generate_slack_config(args.tokens_dir, args.output)
        
        print("\n🎯 Next Steps:")
        print("1. Test configuration with puente.py")
        print("2. Update default_channel if needed")
        print("3. Deploy to production environment")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()