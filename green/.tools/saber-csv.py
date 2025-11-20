#!/usr/bin/env python3
"""
Saber-CSV - CSV-based Ticket Management System
Alternative to saber.py (Linear) - works offline with no external dependencies
Compatible with saber.py API for seamless switching
"""

import os
import csv
import json
import uuid
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

class SaberCSV:
    """CSV-based ticket management system"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug or os.getenv("SABER_CSV_DEBUG", "").lower() in ("true", "1", "yes")
        self.project_prefix = os.getenv("PROJECT_PREFIX", "TKT")
        
        # Storage paths
        self.storage_dir = Path(".spectrum")
        self.csv_path = self.storage_dir / "tickets.csv"
        self.config_path = self.storage_dir / "csv_config.json"
        self.dependencies_path = Path(".ticket_dependencies.json")
        
        # Initialize storage
        self._ensure_storage()
        self._load_config()
    
    def _ensure_storage(self):
        """Ensure storage directory and CSV file exist"""
        self.storage_dir.mkdir(exist_ok=True)
        
        if not self.csv_path.exists():
            # Create CSV with header
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Id", "Identifier", "Title", "Description", "State",
                    "AssigneeName", "AssigneeEmail", "ParentIdentifier",
                    "Labels", "CreatedAt", "UpdatedAt", "Priority"
                ])
            if self.debug:
                print(f"✅ Created CSV file: {self.csv_path}")
    
    def _load_config(self):
        """Load or create configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "project_prefix": self.project_prefix,
                "next_ticket_number": 1,
                "created_at": self._utc_timestamp()
            }
            self._save_config()
    
    def _save_config(self):
        """Save configuration"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _utc_timestamp(self) -> str:
        """Get current UTC timestamp in Excel-compatible format"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    def _escape_csv_field(self, value: str) -> str:
        """
        Escape double quote characters by doubling them per RFC 4180.
        Actual field quoting (for commas/newlines) is handled by csv.QUOTE_ALL in _write_tickets().
        """
        if not value:
            return ""
        return value.replace('"', '""')
    
    def _unescape_csv_field(self, value: str) -> str:
        """Unescape CSV field"""
        if not value:
            return ""
        return value.replace('""', '"')
    
    def _read_tickets(self) -> List[Dict[str, str]]:
        """Read all tickets from CSV"""
        tickets = []
        if not self.csv_path.exists():
            return tickets
        
        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Unescape all fields
                ticket = {k: self._unescape_csv_field(v) for k, v in row.items()}
                tickets.append(ticket)
        
        return tickets
    
    def _write_tickets(self, tickets: List[Dict[str, str]]):
        """Write all tickets to CSV"""
        fieldnames = [
            "Id", "Identifier", "Title", "Description", "State",
            "AssigneeName", "AssigneeEmail", "ParentIdentifier",
            "Labels", "CreatedAt", "UpdatedAt", "Priority"
        ]
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for ticket in tickets:
                # Escape all fields
                escaped_ticket = {k: self._escape_csv_field(str(ticket.get(k, ""))) for k in fieldnames}
                writer.writerow(escaped_ticket)
    
    def _get_next_identifier(self) -> str:
        """Get next ticket identifier (e.g., TKT-1, TKT-2)"""
        next_num = self.config["next_ticket_number"]
        identifier = f"{self.project_prefix}-{next_num}"
        self.config["next_ticket_number"] = next_num + 1
        self._save_config()
        return identifier
    
    def create_ticket(self, title: str, description: str = "", 
                     state: str = "Todo", assignee_name: str = "",
                     assignee_email: str = "", parent_identifier: str = "",
                     labels: List[str] = None, priority: int = 1) -> Dict[str, Any]:
        """Create a new ticket"""
        if labels is None:
            labels = []
        
        ticket_id = str(uuid.uuid4())
        identifier = self._get_next_identifier()
        now = self._utc_timestamp()
        
        new_ticket = {
            "Id": ticket_id,
            "Identifier": identifier,
            "Title": title,
            "Description": description,
            "State": state,
            "AssigneeName": assignee_name,
            "AssigneeEmail": assignee_email,
            "ParentIdentifier": parent_identifier,
            "Labels": ",".join(labels) if labels else "",
            "CreatedAt": now,
            "UpdatedAt": now,
            "Priority": str(priority)
        }
        
        tickets = self._read_tickets()
        tickets.append(new_ticket)
        self._write_tickets(tickets)
        
        if self.debug:
            print(f"✅ Created ticket: {identifier} - {title}")
        
        return {
            "success": True,
            "identifier": identifier,
            "id": ticket_id,
            "url": f"file://{self.csv_path.absolute()}#{identifier}"
        }
    
    def get_ticket(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get a ticket by identifier"""
        tickets = self._read_tickets()
        for ticket in tickets:
            if ticket["Identifier"] == identifier:
                return {
                    "identifier": ticket["Identifier"],
                    "title": ticket["Title"],
                    "description": ticket["Description"],
                    "state": ticket["State"],
                    "assignee": {
                        "name": ticket["AssigneeName"],
                        "email": ticket["AssigneeEmail"]
                    } if ticket["AssigneeName"] else None,
                    "parent": ticket["ParentIdentifier"] if ticket["ParentIdentifier"] else None,
                    "labels": [l.strip() for l in ticket["Labels"].split(",") if l.strip()],
                    "priority": int(ticket["Priority"]) if ticket["Priority"] else 1,
                    "createdAt": ticket["CreatedAt"],
                    "updatedAt": ticket["UpdatedAt"],
                    "url": f"file://{self.csv_path.absolute()}#{identifier}"
                }
        return None
    
    def update_ticket_status(self, identifier: str, state: str) -> bool:
        """Update ticket status"""
        tickets = self._read_tickets()
        updated = False
        
        for ticket in tickets:
            if ticket["Identifier"] == identifier:
                ticket["State"] = state
                ticket["UpdatedAt"] = self._utc_timestamp()
                updated = True
                break
        
        if updated:
            self._write_tickets(tickets)
            if self.debug:
                print(f"✅ Updated {identifier} status to: {state}")
        
        return updated
    
    def add_comment(self, identifier: str, comment: str) -> bool:
        """Add a comment to a ticket (appends to description)"""
        tickets = self._read_tickets()
        updated = False
        
        for ticket in tickets:
            if ticket["Identifier"] == identifier:
                timestamp = self._utc_timestamp()
                comment_entry = f"\n\n---\n**Comment ({timestamp}):**\n{comment}"
                ticket["Description"] = ticket.get("Description", "") + comment_entry
                ticket["UpdatedAt"] = timestamp
                updated = True
                break
        
        if updated:
            self._write_tickets(tickets)
            if self.debug:
                print(f"✅ Added comment to {identifier}")
        
        return updated
    
    def assign_ticket(self, identifier: str, assignee_name: str, assignee_email: str = "") -> bool:
        """Assign a ticket to a user"""
        tickets = self._read_tickets()
        updated = False
        
        for ticket in tickets:
            if ticket["Identifier"] == identifier:
                ticket["AssigneeName"] = assignee_name
                ticket["AssigneeEmail"] = assignee_email
                ticket["UpdatedAt"] = self._utc_timestamp()
                updated = True
                break
        
        if updated:
            self._write_tickets(tickets)
            if self.debug:
                print(f"✅ Assigned {identifier} to: {assignee_name}")
        
        return updated
    
    def add_labels(self, identifier: str, labels: List[str]) -> bool:
        """Add labels to a ticket"""
        tickets = self._read_tickets()
        updated = False
        
        for ticket in tickets:
            if ticket["Identifier"] == identifier:
                existing_labels = set(l.strip() for l in ticket["Labels"].split(",") if l.strip())
                existing_labels.update(labels)
                ticket["Labels"] = ",".join(sorted(existing_labels))
                ticket["UpdatedAt"] = self._utc_timestamp()
                updated = True
                break
        
        if updated:
            self._write_tickets(tickets)
            if self.debug:
                print(f"✅ Added labels to {identifier}: {labels}")
        
        return updated
    
    def remove_labels(self, identifier: str, labels: List[str]) -> bool:
        """Remove labels from a ticket"""
        tickets = self._read_tickets()
        updated = False
        
        for ticket in tickets:
            if ticket["Identifier"] == identifier:
                existing_labels = set(l.strip() for l in ticket["Labels"].split(",") if l.strip())
                existing_labels -= set(labels)
                ticket["Labels"] = ",".join(sorted(existing_labels))
                ticket["UpdatedAt"] = self._utc_timestamp()
                updated = True
                break
        
        if updated:
            self._write_tickets(tickets)
            if self.debug:
                print(f"✅ Removed labels from {identifier}: {labels}")
        
        return updated
    
    def list_tickets(self, state: Optional[str] = None, assignee: Optional[str] = None,
                    labels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """List tickets with optional filters"""
        tickets = self._read_tickets()
        results = []
        
        for ticket_data in tickets:
            # Apply filters
            if state and ticket_data["State"] != state:
                continue
            if assignee and ticket_data["AssigneeName"] != assignee:
                continue
            if labels:
                ticket_labels = set(l.strip() for l in ticket_data["Labels"].split(",") if l.strip())
                if not all(label in ticket_labels for label in labels):
                    continue
            
            # Convert to output format
            ticket = {
                "identifier": ticket_data["Identifier"],
                "title": ticket_data["Title"],
                "state": ticket_data["State"],
                "assignee": ticket_data["AssigneeName"] if ticket_data["AssigneeName"] else None,
                "labels": [l.strip() for l in ticket_data["Labels"].split(",") if l.strip()],
                "priority": int(ticket_data["Priority"]) if ticket_data["Priority"] else 1,
                "url": f"file://{self.csv_path.absolute()}#{ticket_data['Identifier']}"
            }
            results.append(ticket)
        
        return results
    
    def get_children(self, parent_identifier: str) -> List[Dict[str, Any]]:
        """Get child tickets of a parent ticket"""
        tickets = self._read_tickets()
        children = []
        
        for ticket_data in tickets:
            if ticket_data["ParentIdentifier"] == parent_identifier:
                ticket = {
                    "identifier": ticket_data["Identifier"],
                    "title": ticket_data["Title"],
                    "state": ticket_data["State"],
                    "assignee": ticket_data["AssigneeName"] if ticket_data["AssigneeName"] else None
                }
                children.append(ticket)
        
        return children
    
    def has_children(self, identifier: str) -> bool:
        """Check if a ticket has children"""
        tickets = self._read_tickets()
        for ticket in tickets:
            if ticket["ParentIdentifier"] == identifier:
                return True
        return False


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Saber-CSV - CSV Ticket Management")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create ticket
    create_parser = subparsers.add_parser("create", help="Create a new ticket")
    create_parser.add_argument("title", help="Ticket title")
    create_parser.add_argument("--description", "-d", default="", help="Ticket description")
    create_parser.add_argument("--state", "-s", default="Todo", help="Initial state")
    create_parser.add_argument("--assignee", "-a", default="", help="Assignee name")
    create_parser.add_argument("--labels", "-l", default="", help="Comma-separated labels")
    create_parser.add_argument("--priority", "-p", type=int, default=1, help="Priority (1-4)")
    
    # Get ticket
    get_parser = subparsers.add_parser("get", help="Get ticket details")
    get_parser.add_argument("identifier", help="Ticket identifier (e.g., TKT-1)")
    
    # Update status
    status_parser = subparsers.add_parser("status", help="Update ticket status")
    status_parser.add_argument("identifier", help="Ticket identifier")
    status_parser.add_argument("state", help="New state")
    
    # Add comment
    comment_parser = subparsers.add_parser("comment", help="Add comment to ticket")
    comment_parser.add_argument("identifier", help="Ticket identifier")
    comment_parser.add_argument("comment", help="Comment text")
    
    # Assign
    assign_parser = subparsers.add_parser("assign", help="Assign ticket")
    assign_parser.add_argument("identifier", help="Ticket identifier")
    assign_parser.add_argument("assignee", help="Assignee name")
    
    # List
    list_parser = subparsers.add_parser("list", help="List tickets")
    list_parser.add_argument("--state", "-s", help="Filter by state")
    list_parser.add_argument("--assignee", "-a", help="Filter by assignee")
    list_parser.add_argument("--labels", "-l", help="Filter by labels (comma-separated)")
    
    # Add labels
    label_add_parser = subparsers.add_parser("add-label", help="Add labels to ticket")
    label_add_parser.add_argument("identifier", help="Ticket identifier")
    label_add_parser.add_argument("labels", help="Comma-separated labels to add")
    
    # Remove labels
    label_remove_parser = subparsers.add_parser("remove-label", help="Remove labels from ticket")
    label_remove_parser.add_argument("identifier", help="Ticket identifier")
    label_remove_parser.add_argument("labels", help="Comma-separated labels to remove")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    saber_csv = SaberCSV(debug=args.debug)
    
    # Execute command
    if args.command == "create":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()] if args.labels else []
        result = saber_csv.create_ticket(
            title=args.title,
            description=args.description,
            state=args.state,
            assignee_name=args.assignee,
            labels=labels,
            priority=args.priority
        )
        print(json.dumps(result, indent=2))
    
    elif args.command == "get":
        ticket = saber_csv.get_ticket(args.identifier)
        if ticket:
            print(json.dumps(ticket, indent=2))
        else:
            print(f"❌ Ticket not found: {args.identifier}")
            sys.exit(1)
    
    elif args.command == "status":
        if saber_csv.update_ticket_status(args.identifier, args.state):
            print(f"✅ Updated {args.identifier} to {args.state}")
        else:
            print(f"❌ Failed to update {args.identifier}")
            sys.exit(1)
    
    elif args.command == "comment":
        if saber_csv.add_comment(args.identifier, args.comment):
            print(f"✅ Added comment to {args.identifier}")
        else:
            print(f"❌ Failed to add comment to {args.identifier}")
            sys.exit(1)
    
    elif args.command == "assign":
        if saber_csv.assign_ticket(args.identifier, args.assignee):
            print(f"✅ Assigned {args.identifier} to {args.assignee}")
        else:
            print(f"❌ Failed to assign {args.identifier}")
            sys.exit(1)
    
    elif args.command == "list":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()] if args.labels else None
        tickets = saber_csv.list_tickets(state=args.state, assignee=args.assignee, labels=labels)
        print(json.dumps(tickets, indent=2))
    
    elif args.command == "add-label":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()]
        if saber_csv.add_labels(args.identifier, labels):
            print(f"✅ Added labels to {args.identifier}")
        else:
            print(f"❌ Failed to add labels to {args.identifier}")
            sys.exit(1)
    
    elif args.command == "remove-label":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()]
        if saber_csv.remove_labels(args.identifier, labels):
            print(f"✅ Removed labels from {args.identifier}")
        else:
            print(f"❌ Failed to remove labels from {args.identifier}")
            sys.exit(1)


if __name__ == "__main__":
    main()
