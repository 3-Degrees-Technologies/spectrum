#!/usr/bin/env python3
"""
Saber - The Ultimate Linear Management Tool
Unified tool for all Linear API operations
"""

import os
import json
import requests
import sys
from typing import Optional, Dict, Any, List
from pathlib import Path

class Saber:
    def __init__(self, debug: bool = False):
        self.api_key = self._get_api_key()
        self.api_url = "https://api.linear.app/graphql"
        self.team_id = self._get_team_id()
        self.debug = debug or os.getenv("SABER_DEBUG", "").lower() in ("true", "1", "yes")
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _get_api_key(self) -> str:
        """Get API key from environment or .env file"""
        api_key = os.getenv("LINEAR_API_KEY")
        if api_key:
            return api_key
        
        # Fallback to .env file
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("LINEAR_API_KEY"):
                    return line.split("=")[1].strip().strip('"')
        
        raise Exception("LINEAR_API_KEY not found in environment or .env file")
    
    def _get_team_id(self) -> str:
        """Get team ID from environment or .env file"""
        team_id = os.getenv("LINEAR_TEAM_ID")
        if team_id:
            return team_id
        
        # Fallback to .env file
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("LINEAR_TEAM_ID"):
                    return line.split("=")[1].strip().strip('"')
        
        # No default fallback - require LINEAR_TEAM_ID to be set
        raise Exception("LINEAR_TEAM_ID not found in environment or .env file. Please set LINEAR_TEAM_ID environment variable.")
    
    def _execute_query(self, query: str, variables: Dict = None) -> Dict:
        """Execute GraphQL query/mutation with enhanced error handling"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        if self.debug:
            print(f"🔍 DEBUG: Executing GraphQL operation")
            print(f"📡 Query: {query.strip()}")
            if variables:
                print(f"📝 Variables: {json.dumps(variables, indent=2)}")
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            
            if self.debug:
                print(f"📨 Response Status: {response.status_code}")
                print(f"📄 Response Headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            result = response.json()
            
            if self.debug:
                print(f"📊 Response Data: {json.dumps(result, indent=2)}")
            
            if "errors" in result:
                error_details = []
                for error in result["errors"]:
                    error_msg = error.get("message", "Unknown error")
                    locations = error.get("locations", [])
                    extensions = error.get("extensions", {})
                    
                    error_detail = f"GraphQL Error: {error_msg}"
                    if locations:
                        error_detail += f" (at line {locations[0].get('line', '?')}, col {locations[0].get('column', '?')})"
                    if extensions.get("code"):
                        error_detail += f" [Code: {extensions['code']}]"
                    
                    error_details.append(error_detail)
                
                full_error = "\n".join(error_details)
                if self.debug:
                    print(f"❌ GraphQL Errors: {full_error}")
                
                raise Exception(f"GraphQL operation failed:\n{full_error}")
            
            return result["data"]
            
        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP request failed: {e}"
            if self.debug:
                print(f"❌ HTTP Error: {error_msg}")
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response: {e}"
            if self.debug:
                print(f"❌ JSON Error: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            if self.debug:
                print(f"❌ Unexpected Error: {e}")
            raise
    
    # CORE OPERATIONS
    
    def create_ticket(self, title: str, description: str, 
                     state: str = "Todo", priority: int = 0) -> Dict:
        """Create a new ticket with enhanced validation"""
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")
        if not description or not description.strip():
            raise ValueError("Description cannot be empty")
        if priority < 0 or priority > 4:
            raise ValueError("Priority must be between 0 (no priority) and 4 (urgent)")
        
        query = """
        mutation CreateIssue($teamId: String!, $title: String!, $description: String!, 
                           $stateId: String, $priority: Int!) {
            issueCreate(input: {
                teamId: $teamId,
                title: $title,
                description: $description,
                stateId: $stateId,
                priority: $priority
            }) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                }
            }
        }
        """
        
        try:
            # Get state ID for the state name
            state_id = self._get_state_id(state)
        except Exception as e:
            raise Exception(f"Invalid state '{state}'. Available states: Todo, In Progress, Done, Backlog, Canceled, Duplicate. Error: {e}")
        
        variables = {
            "teamId": self.team_id,
            "title": title.strip(),
            "description": description.strip(),
            "stateId": state_id,
            "priority": priority
        }
        
        result = self._execute_query(query, variables)
        if not result.get("issueCreate", {}).get("success"):
            raise Exception("Failed to create ticket - API returned success=false")
        
        return result["issueCreate"]["issue"]
    
    def get_ticket(self, identifier: str) -> Dict:
        """Get ticket details by identifier (e.g., SIG-123)"""
        if not identifier or "-" not in identifier:
            raise ValueError(f"Invalid ticket identifier: {identifier}. Expected format: XXX-123")
        
        try:
            ticket_number = int(identifier.split("-")[1])
        except (IndexError, ValueError):
            raise ValueError(f"Invalid ticket identifier format: {identifier}. Expected format: XXX-123")
        
        search_query = """
        query SearchIssue($filter: IssueFilter!) {
            issues(filter: $filter, first: 1) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    assignee { name email }
                    parent { identifier title }
                    labels { nodes { id name color } }
                    children {
                        nodes {
                            id
                            identifier
                            title
                            state { name }
                        }
                    }
                    createdAt
                    updatedAt
                }
            }
        }
        """
        
        variables = {
            "filter": {
                "team": {"id": {"eq": self.team_id}},
                "number": {"eq": ticket_number}
            }
        }
        
        result = self._execute_query(search_query, variables)
        issues = result["issues"]["nodes"]
        
        if not issues:
            raise Exception(f"Ticket {identifier} not found. Please verify the ticket exists and you have access to it.")
        
        return issues[0]
    
    def update_ticket_status(self, identifier: str, status: str) -> bool:
        """Update ticket status"""
        ticket = self.get_ticket(identifier)
        state_id = self._get_state_id(status)
        
        query = """
        mutation UpdateIssue($issueId: String!, $stateId: String!) {
            issueUpdate(id: $issueId, input: {stateId: $stateId}) {
                success
            }
        }
        """
        
        variables = {
            "issueId": ticket["id"],
            "stateId": state_id
        }
        
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def update_ticket_description(self, identifier: str, description: str) -> bool:
        """Update ticket description"""
        ticket = self.get_ticket(identifier)
        
        query = """
        mutation UpdateIssue($issueId: String!, $description: String!) {
            issueUpdate(id: $issueId, input: {description: $description}) {
                success
            }
        }
        """
        
        variables = {
            "issueId": ticket["id"],
            "description": description
        }
        
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def add_comment(self, identifier: str, comment: str) -> bool:
        """Add comment to ticket"""
        ticket = self.get_ticket(identifier)
        
        query = """
        mutation CommentCreate($issueId: String!, $body: String!) {
            commentCreate(input: {issueId: $issueId, body: $body}) {
                success
                comment {
                    id
                    body
                }
            }
        }
        """
        
        variables = {
            "issueId": ticket["id"],
            "body": comment
        }
        
        result = self._execute_query(query, variables)
        return result["commentCreate"]["success"]
    
    def set_parent_child(self, child_identifier: str, parent_identifier: str) -> bool:
        """Set parent-child relationship between tickets"""
        child = self.get_ticket(child_identifier)
        parent = self.get_ticket(parent_identifier)
        
        query = """
        mutation UpdateIssue($issueId: String!, $parentId: String!) {
            issueUpdate(id: $issueId, input: {parentId: $parentId}) {
                success
            }
        }
        """
        
        variables = {
            "issueId": child["id"],
            "parentId": parent["id"]
        }
        
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def remove_parent(self, child_identifier: str) -> bool:
        """Remove parent relationship from ticket"""
        child = self.get_ticket(child_identifier)
        
        query = """
        mutation UpdateIssue($issueId: String!) {
            issueUpdate(id: $issueId, input: {parentId: null}) {
                success
            }
        }
        """
        
        variables = {"issueId": child["id"]}
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def assign_ticket(self, identifier: str, assignee_email: str) -> bool:
        """Assign ticket to user by email"""
        ticket = self.get_ticket(identifier)
        user_id = self._get_user_id_by_email(assignee_email)
        
        query = """
        mutation UpdateIssue($issueId: String!, $assigneeId: String!) {
            issueUpdate(id: $issueId, input: {assigneeId: $assigneeId}) {
                success
            }
        }
        """
        
        variables = {
            "issueId": ticket["id"],
            "assigneeId": user_id
        }
        
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def list_tickets(self, status: str = None, assignee: str = None) -> List[Dict]:
        """List tickets with optional filtering"""
        query = """
        query ListIssues($filter: IssueFilter!) {
            issues(filter: $filter) {
                nodes {
                    id
                    identifier
                    title
                    state { name }
                    assignee { name email }
                    updatedAt
                }
            }
        }
        """
        
        variables = {
            "filter": {
                "team": {"id": {"eq": self.team_id}}
            }
        }
        
        result = self._execute_query(query, variables)
        tickets = result["issues"]["nodes"]
        
        # Apply filtering in Python 
        if status:
            tickets = [t for t in tickets if t["state"]["name"].lower() == status.lower()]
        
        if assignee:
            tickets = [t for t in tickets if t.get("assignee") and t["assignee"]["email"] == assignee]
        
        return tickets
    
    # LABEL OPERATIONS
    
    def get_labels(self) -> List[Dict]:
        """Get all labels for the team"""
        query = """
        query GetLabels($teamId: ID!) {
            issueLabels(filter: {team: {id: {eq: $teamId}}}) {
                nodes {
                    id
                    name
                    color
                    description
                }
            }
        }
        """
        
        variables = {"teamId": self.team_id}
        result = self._execute_query(query, variables)
        return result["issueLabels"]["nodes"]
    
    def create_label(self, name: str, color: str = "#6b7280", description: str = "") -> Dict:
        """Create a new label"""
        query = """
        mutation CreateLabel($teamId: String!, $name: String!, $color: String!, $description: String) {
            issueLabelCreate(input: {
                teamId: $teamId,
                name: $name,
                color: $color,
                description: $description
            }) {
                success
                issueLabel {
                    id
                    name
                    color
                }
            }
        }
        """
        
        variables = {
            "teamId": self.team_id,
            "name": name,
            "color": color,
            "description": description
        }
        
        result = self._execute_query(query, variables)
        return result["issueLabelCreate"]["issueLabel"]
    
    def add_labels_to_ticket(self, identifier: str, label_names: List[str]) -> bool:
        """Add labels to ticket"""
        ticket = self.get_ticket(identifier)
        all_labels = self.get_labels()
        
        # Find label IDs by name
        label_ids = []
        for label_name in label_names:
            for label in all_labels:
                if label["name"].lower() == label_name.lower():
                    label_ids.append(label["id"])
                    break
            else:
                raise Exception(f"Label '{label_name}' not found")
        
        # Get existing label IDs
        existing_label_ids = [label["id"] for label in ticket.get("labels", {}).get("nodes", [])]
        
        # Combine existing and new labels
        all_label_ids = list(set(existing_label_ids + label_ids))
        
        query = """
        mutation UpdateIssue($issueId: String!, $labelIds: [String!]!) {
            issueUpdate(id: $issueId, input: {labelIds: $labelIds}) {
                success
            }
        }
        """
        
        variables = {
            "issueId": ticket["id"],
            "labelIds": all_label_ids
        }
        
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def remove_labels_from_ticket(self, identifier: str, label_names: List[str]) -> bool:
        """Remove labels from ticket"""
        ticket = self.get_ticket(identifier)
        
        # Get existing labels
        existing_labels = ticket.get("labels", {}).get("nodes", [])
        
        # Filter out labels to remove
        remaining_label_ids = []
        for label in existing_labels:
            if label["name"].lower() not in [name.lower() for name in label_names]:
                remaining_label_ids.append(label["id"])
        
        query = """
        mutation UpdateIssue($issueId: String!, $labelIds: [String!]!) {
            issueUpdate(id: $issueId, input: {labelIds: $labelIds}) {
                success
            }
        }
        """
        
        variables = {
            "issueId": ticket["id"],
            "labelIds": remaining_label_ids
        }
        
        result = self._execute_query(query, variables)
        return result["issueUpdate"]["success"]
    
    def list_ticket_labels(self, identifier: str) -> List[Dict]:
        """List labels on a ticket"""
        ticket = self.get_ticket(identifier)
        return ticket.get("labels", {}).get("nodes", [])
    
    # EPIC OPERATIONS
    
    def create_epic_structure(self, epic_identifier: str, subtask_identifiers: List[str]) -> bool:
        """Create parent-child relationships for an epic and its subtasks"""
        epic = self.get_ticket(epic_identifier)
        
        for subtask_id in subtask_identifiers:
            try:
                self.set_parent_child(subtask_id, epic_identifier)
                print(f"✅ Linked {subtask_id} to {epic_identifier}")
            except Exception as e:
                print(f"❌ Failed to link {subtask_id}: {e}")
                return False
        
        return True
    
    def get_epic_structure(self, epic_identifier: str) -> Dict:
        """Get epic with all its subtasks"""
        epic = self.get_ticket(epic_identifier)
        return {
            "epic": epic,
            "subtasks": epic.get("children", {}).get("nodes", [])
        }
    
    def get_project_prefix(self) -> str:
        """Get project prefix from team info"""
        query = """
        query GetTeam($teamId: String!) {
            team(id: $teamId) {
                id
                name
                key
            }
        }
        """
        
        variables = {"teamId": self.team_id}
        result = self._execute_query(query, variables)
        team = result["team"]
        
        # Return the team key (project prefix)
        return team["key"]
    
    def save_project_config(self) -> str:
        """Save project configuration including prefix"""
        prefix = self.get_project_prefix()
        
        config = {
            "project_prefix": prefix,
            "team_id": self.team_id,
            "updated_at": os.path.basename(__file__)
        }
        
        # Save to .spectrum directory
        config_dir = Path(".spectrum")
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "linear_config.json"
        
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        if self.debug:
            print(f"💾 Saved config to {config_file}: {config}")
        
        return prefix

    # UTILITY OPERATIONS
    
    def _get_state_id(self, state_name: str) -> str:
        """Get state ID by name with enhanced error reporting"""
        if not state_name:
            raise ValueError("State name cannot be empty")
        
        query = """
        query GetStates($teamId: ID!) {
            workflowStates(filter: {team: {id: {eq: $teamId}}}) {
                nodes {
                    id
                    name
                }
            }
        }
        """
        
        result = self._execute_query(query, {"teamId": self.team_id})
        states = result["workflowStates"]["nodes"]
        
        if self.debug:
            print(f"🔍 Available states: {[s['name'] for s in states]}")
        
        for state in states:
            if state["name"].lower() == state_name.lower():
                return state["id"]
        
        available_states = [s["name"] for s in states]
        raise Exception(f"State '{state_name}' not found. Available states: {', '.join(available_states)}")
    
    def _get_user_id_by_email(self, email: str) -> str:
        """Get user ID by email with enhanced validation"""
        if not email or "@" not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        query = """
        query GetUsers {
            users {
                nodes {
                    id
                    email
                    name
                }
            }
        }
        """
        
        result = self._execute_query(query)
        users = result["users"]["nodes"]
        
        if self.debug:
            print(f"🔍 Available users: {[u['email'] for u in users]}")
        
        for user in users:
            if user["email"].lower() == email.lower():
                return user["id"]
        
        available_emails = [u["email"] for u in users]
        raise Exception(f"User with email '{email}' not found. Available users: {', '.join(available_emails)}")

# CLI INTERFACE

def main():
    if len(sys.argv) < 2:
        print("""
Saber - The Ultimate Linear Management Tool

Usage:
    python3 saber.py create "Title" "Description" [status] [priority]
    python3 saber.py get XXX-123
    python3 saber.py status XXX-123 "In Progress"
    python3 saber.py description XXX-123 "New description"
    python3 saber.py comment XXX-123 "Progress update"
    python3 saber.py parent XXX-123 XXX-456
    python3 saber.py unparent XXX-123
    python3 saber.py assign XXX-123 user@example.com
    python3 saber.py list [status] [assignee@email.com]
    python3 saber.py epic XXX-123 XXX-124,XXX-125,XXX-126
    
    Label operations:
    python3 saber.py labels                           # List all labels
    python3 saber.py labels XXX-123                   # List ticket labels
    python3 saber.py label XXX-123 add "bug,urgent"  # Add labels
    python3 saber.py label XXX-123 remove "wip"      # Remove labels
    python3 saber.py create-label "new-label" "#ff0000" "Description"

Environment variables:
    SABER_DEBUG=true                                  # Enable debug output
    LINEAR_API_KEY=lin_api_xxx                        # Set API key (required)
    LINEAR_TEAM_ID=team-uuid                          # Set team ID (required)
        """)
        sys.exit(1)
    
    # Check for debug flag
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        sys.argv.remove("--debug")
    
    saber = Saber(debug=debug_mode)
    command = sys.argv[1]
    
    try:
        if command == "create":
            title = sys.argv[2]
            description = sys.argv[3]
            status = sys.argv[4] if len(sys.argv) > 4 else "Todo"
            priority = int(sys.argv[5]) if len(sys.argv) > 5 else 0
            
            result = saber.create_ticket(title, description, status, priority)
            print(f"✅ Created {result['identifier']}: {result['title']}")
            print(f"🔗 URL: {result['url']}")
        
        elif command == "get":
            identifier = sys.argv[2]
            result = saber.get_ticket(identifier)
            print(json.dumps(result, indent=2))
        
        elif command == "status":
            identifier = sys.argv[2]
            status = sys.argv[3]
            success = saber.update_ticket_status(identifier, status)
            print(f"✅ Updated {identifier} status to {status}" if success else f"❌ Failed to update {identifier}")
        
        elif command == "description":
            identifier = sys.argv[2]
            description = sys.argv[3]
            success = saber.update_ticket_description(identifier, description)
            print(f"✅ Updated {identifier} description" if success else f"❌ Failed to update {identifier}")
        
        elif command == "comment":
            identifier = sys.argv[2]
            comment = sys.argv[3]
            success = saber.add_comment(identifier, comment)
            print(f"✅ Added comment to {identifier}" if success else f"❌ Failed to add comment to {identifier}")
        
        elif command == "parent":
            child = sys.argv[2]
            parent = sys.argv[3]
            success = saber.set_parent_child(child, parent)
            print(f"✅ Set {child} as child of {parent}" if success else f"❌ Failed to set parent relationship")
        
        elif command == "unparent":
            child = sys.argv[2]
            success = saber.remove_parent(child)
            print(f"✅ Removed parent from {child}" if success else f"❌ Failed to remove parent")
        
        elif command == "assign":
            identifier = sys.argv[2]
            assignee = sys.argv[3]
            success = saber.assign_ticket(identifier, assignee)
            print(f"✅ Assigned {identifier} to {assignee}" if success else f"❌ Failed to assign {identifier}")
        
        elif command == "list":
            status = sys.argv[2] if len(sys.argv) > 2 else None
            assignee = sys.argv[3] if len(sys.argv) > 3 else None
            tickets = saber.list_tickets(status, assignee)
            
            for ticket in tickets:
                print(f"{ticket['identifier']}: {ticket['title']} [{ticket['state']['name']}]")
        
        elif command == "epic":
            epic_id = sys.argv[2]
            subtasks = sys.argv[3].split(",")
            success = saber.create_epic_structure(epic_id, subtasks)
            print(f"✅ Created epic structure for {epic_id}" if success else f"❌ Failed to create epic structure")
        
        elif command == "labels":
            if len(sys.argv) == 2:
                # List all labels
                labels = saber.get_labels()
                for label in labels:
                    print(f"{label['name']} ({label['color']})")
            else:
                # List ticket labels
                identifier = sys.argv[2]
                labels = saber.list_ticket_labels(identifier)
                for label in labels:
                    print(f"{label['name']} ({label['color']})")
        
        elif command == "label":
            identifier = sys.argv[2]
            action = sys.argv[3]
            label_names = sys.argv[4].split(",")
            
            if action == "add":
                success = saber.add_labels_to_ticket(identifier, label_names)
                print(f"✅ Added labels to {identifier}" if success else f"❌ Failed to add labels")
            elif action == "remove":
                success = saber.remove_labels_from_ticket(identifier, label_names)
                print(f"✅ Removed labels from {identifier}" if success else f"❌ Failed to remove labels")
            else:
                print(f"Unknown label action: {action}")
        
        elif command == "create-label":
            name = sys.argv[2]
            color = sys.argv[3] if len(sys.argv) > 3 else "#6b7280"
            description = sys.argv[4] if len(sys.argv) > 4 else ""
            
            result = saber.create_label(name, color, description)
            print(f"✅ Created label: {result['name']} ({result['color']})")
        
        elif command == "config":
            prefix = saber.save_project_config()
            print(f"✅ Saved project config - Prefix: {prefix}")
        
        elif command == "prefix":
            try:
                # Try to load from config first
                config_file = Path(".spectrum/linear_config.json")
                if config_file.exists():
                    with open(config_file) as f:
                        config = json.load(f)
                    print(config["project_prefix"])
                else:
                    # Get from API and save
                    prefix = saber.get_project_prefix()
                    saber.save_project_config()
                    print(prefix)
            except Exception as e:
                print(f"❌ Error getting prefix: {e}")
                sys.exit(1)
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()