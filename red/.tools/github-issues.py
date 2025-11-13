#!/usr/bin/env python3
"""
GitHub Issues Integration for Spectrum
Python wrapper around GitHub CLI (gh) for issue management
Compatible with GitHub Issues functionality
"""

import os
import json
import subprocess
import sys
from typing import Optional, Dict, Any, List
from pathlib import Path
import urllib.parse

class GitHubIssues:
    """GitHub Issues management using gh CLI"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug or os.getenv("GITHUB_DEBUG", "").lower() in ("true", "1", "yes")
        self.config_path = Path(".spectrum") / "github_config.json"
        self._ensure_gh_installed()
        self._load_config()
    
    def _ensure_gh_installed(self):
        """Check if gh CLI is installed and authenticated"""
        try:
            subprocess.run(["gh", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ GitHub CLI (gh) not found. Please install it:")
            print("   https://cli.github.com/")
            sys.exit(1)
        
        # Check authentication
        try:
            result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ GitHub CLI not authenticated. Please run:")
                print("   gh auth login")
                sys.exit(1)
        except subprocess.CalledProcessError:
            print("❌ GitHub authentication failed. Please run:")
            print("   gh auth login")
            sys.exit(1)
    
    def _load_config(self):
        """Load or create configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        else:
            # Auto-detect from git remote
            owner, repo = self._detect_repo()
            self.config = {
                "default_owner": owner,
                "default_repo": repo,
                "workflow_labels": [
                    "status:todo",
                    "status:in-progress",
                    "status:review",
                    "status:done"
                ]
            }
            self._save_config()
    
    def _save_config(self):
        """Save configuration"""
        Path(".spectrum").mkdir(exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _detect_repo(self) -> tuple[str, str]:
        """Auto-detect owner/repo from git remote"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
            
            # Parse GitHub URL (supports both HTTPS and SSH)
            # Parse for SSH ("git@github.com:owner/repo.git") or HTTPS ("https://github.com/owner/repo.git")
            host = ""
            if remote_url.startswith("git@"):
                # SSH format: git@github.com:owner/repo.git
                try:
                    host_and_path = remote_url.split("git@", 1)[1]
                    host, path = host_and_path.split(":", 1)
                except ValueError:
                    host = ""
                    path = ""
            else:
                # HTTPS or other
                parsed = urllib.parse.urlparse(remote_url)
                host = parsed.hostname
                path = parsed.path
            if host == "github.com" and path:
                # Split path to get owner/repo
                parts = path.strip("/").split("/")
                if len(parts) >= 2:
                    owner = parts[-2]
                    repo = parts[-1].replace(".git", "")
                    if self.debug:
                        print(f"🔍 Detected repo: {owner}/{repo}")
                    return owner, repo
        except subprocess.CalledProcessError:
            pass
        
        return "", ""
    
    def _run_gh(self, args: List[str]) -> Dict[str, Any]:
        """Run gh CLI command and return JSON output"""
        try:
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                check=True
            )
            
            if self.debug:
                print(f"🔍 gh {' '.join(args)}")
                print(f"📄 Output: {result.stdout[:200]}")
            
            # Try to parse as JSON
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"output": result.stdout.strip()}
        
        except subprocess.CalledProcessError as e:
            print(f"❌ GitHub CLI error: {e.stderr}")
            sys.exit(1)
    
    def _parse_issue_ref(self, issue_ref: str) -> tuple[Optional[str], Optional[str], int]:
        """Parse issue reference (e.g., #123, owner/repo#123)"""
        owner = self.config.get("default_owner")
        repo = self.config.get("default_repo")
        
        # Format: owner/repo#123
        if "/" in issue_ref and "#" in issue_ref:
            repo_part, num_part = issue_ref.split("#")
            owner, repo = repo_part.split("/")
            number = int(num_part)
        # Format: #123
        elif issue_ref.startswith("#"):
            number = int(issue_ref[1:])
        else:
            number = int(issue_ref)
        
        return owner, repo, number
    
    def create_issue(self, title: str, body: str = "", labels: List[str] = None,
                    assignee: str = "") -> Dict[str, Any]:
        """Create a new GitHub issue"""
        args = ["issue", "create", "--title", title]
        
        if body:
            args.extend(["--body", body])
        
        if labels:
            args.extend(["--label", ",".join(labels)])
        
        if assignee:
            args.extend(["--assignee", assignee])
        
        if self.config.get("default_repo"):
            args.extend(["--repo", f"{self.config['default_owner']}/{self.config['default_repo']}"])
        
        result = self._run_gh(args)
        
        if self.debug:
            print(f"✅ Created issue: {title}")
        
        return result
    
    def get_issue(self, issue_ref: str) -> Optional[Dict[str, Any]]:
        """Get issue details"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        args = [
            "issue", "view", str(number),
            "--json", "number,title,body,state,assignees,labels,comments,createdAt,updatedAt,url"
        ]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        return self._run_gh(args)
    
    def update_issue_state(self, issue_ref: str, state: str) -> bool:
        """Update issue state (open/closed)"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        command = "close" if state.lower() == "closed" else "reopen"
        args = ["issue", command, str(number)]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        self._run_gh(args)
        
        if self.debug:
            print(f"✅ Updated issue #{number} state to: {state}")
        
        return True
    
    def update_issue_body(self, issue_ref: str, body: str) -> bool:
        """Update issue description/body"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        args = ["issue", "edit", str(number), "--body", body]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        self._run_gh(args)
        
        if self.debug:
            print(f"✅ Updated issue #{number} body")
        
        return True
    
    def add_comment(self, issue_ref: str, comment: str) -> bool:
        """Add a comment to an issue"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        args = ["issue", "comment", str(number), "--body", comment]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        self._run_gh(args)
        
        if self.debug:
            print(f"✅ Added comment to issue #{number}")
        
        return True
    
    def assign_issue(self, issue_ref: str, assignee: str) -> bool:
        """Assign an issue to a user"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        args = ["issue", "edit", str(number), "--add-assignee", assignee]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        self._run_gh(args)
        
        if self.debug:
            print(f"✅ Assigned issue #{number} to: {assignee}")
        
        return True
    
    def list_issues(self, state: str = "open", assignee: str = "",
                   labels: List[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """List issues with filters"""
        args = [
            "issue", "list",
            "--json", "number,title,state,assignees,labels,url",
            "--limit", str(limit),
            "--state", state
        ]
        
        if assignee:
            args.extend(["--assignee", assignee])
        
        if labels:
            args.extend(["--label", ",".join(labels)])
        
        if self.config.get("default_repo"):
            args.extend(["--repo", f"{self.config['default_owner']}/{self.config['default_repo']}"])
        
        result = self._run_gh(args)
        
        # gh issue list returns a list directly
        if isinstance(result, list):
            return result
        return []
    
    def add_labels(self, issue_ref: str, labels: List[str]) -> bool:
        """Add labels to an issue"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        args = ["issue", "edit", str(number), "--add-label", ",".join(labels)]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        self._run_gh(args)
        
        if self.debug:
            print(f"✅ Added labels to issue #{number}: {labels}")
        
        return True
    
    def remove_labels(self, issue_ref: str, labels: List[str]) -> bool:
        """Remove labels from an issue"""
        owner, repo, number = self._parse_issue_ref(issue_ref)
        
        args = ["issue", "edit", str(number), "--remove-label", ",".join(labels)]
        
        if owner and repo:
            args.extend(["--repo", f"{owner}/{repo}"])
        
        self._run_gh(args)
        
        if self.debug:
            print(f"✅ Removed labels from issue #{number}: {labels}")
        
        return True


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Issues Management")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create issue
    create_parser = subparsers.add_parser("create", help="Create a new issue")
    create_parser.add_argument("title", help="Issue title")
    create_parser.add_argument("--body", "-b", default="", help="Issue body/description")
    create_parser.add_argument("--labels", "-l", default="", help="Comma-separated labels")
    create_parser.add_argument("--assignee", "-a", default="", help="Assignee username")
    
    # Get issue
    get_parser = subparsers.add_parser("get", help="Get issue details")
    get_parser.add_argument("issue", help="Issue reference (e.g., #123, owner/repo#123)")
    
    # Update state
    status_parser = subparsers.add_parser("status", help="Update issue state")
    status_parser.add_argument("issue", help="Issue reference")
    status_parser.add_argument("state", choices=["open", "closed"], help="New state")
    
    # Update body
    body_parser = subparsers.add_parser("body", help="Update issue body")
    body_parser.add_argument("issue", help="Issue reference")
    body_parser.add_argument("body", help="New body text")
    
    # Add comment
    comment_parser = subparsers.add_parser("comment", help="Add comment to issue")
    comment_parser.add_argument("issue", help="Issue reference")
    comment_parser.add_argument("comment", help="Comment text")
    
    # Assign
    assign_parser = subparsers.add_parser("assign", help="Assign issue")
    assign_parser.add_argument("issue", help="Issue reference")
    assign_parser.add_argument("assignee", help="Assignee username")
    
    # List
    list_parser = subparsers.add_parser("list", help="List issues")
    list_parser.add_argument("--state", "-s", default="open", help="Filter by state")
    list_parser.add_argument("--assignee", "-a", help="Filter by assignee")
    list_parser.add_argument("--labels", "-l", help="Filter by labels (comma-separated)")
    list_parser.add_argument("--limit", "-n", type=int, default=30, help="Max number of issues")
    
    # Add labels
    label_add_parser = subparsers.add_parser("add-label", help="Add labels to issue")
    label_add_parser.add_argument("issue", help="Issue reference")
    label_add_parser.add_argument("labels", help="Comma-separated labels to add")
    
    # Remove labels
    label_remove_parser = subparsers.add_parser("remove-label", help="Remove labels from issue")
    label_remove_parser.add_argument("issue", help="Issue reference")
    label_remove_parser.add_argument("labels", help="Comma-separated labels to remove")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    gh = GitHubIssues(debug=args.debug)
    
    # Execute command
    if args.command == "create":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()] if args.labels else []
        result = gh.create_issue(
            title=args.title,
            body=args.body,
            labels=labels,
            assignee=args.assignee
        )
        print(json.dumps(result, indent=2))
    
    elif args.command == "get":
        issue = gh.get_issue(args.issue)
        if issue:
            print(json.dumps(issue, indent=2))
        else:
            print(f"❌ Issue not found: {args.issue}")
            sys.exit(1)
    
    elif args.command == "status":
        if gh.update_issue_state(args.issue, args.state):
            print(f"✅ Updated {args.issue} to {args.state}")
        else:
            print(f"❌ Failed to update {args.issue}")
            sys.exit(1)
    
    elif args.command == "body":
        if gh.update_issue_body(args.issue, args.body):
            print(f"✅ Updated body for {args.issue}")
        else:
            print(f"❌ Failed to update body for {args.issue}")
            sys.exit(1)
    
    elif args.command == "comment":
        if gh.add_comment(args.issue, args.comment):
            print(f"✅ Added comment to {args.issue}")
        else:
            print(f"❌ Failed to add comment to {args.issue}")
            sys.exit(1)
    
    elif args.command == "assign":
        if gh.assign_issue(args.issue, args.assignee):
            print(f"✅ Assigned {args.issue} to {args.assignee}")
        else:
            print(f"❌ Failed to assign {args.issue}")
            sys.exit(1)
    
    elif args.command == "list":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()] if args.labels else None
        issues = gh.list_issues(
            state=args.state,
            assignee=args.assignee,
            labels=labels,
            limit=args.limit
        )
        print(json.dumps(issues, indent=2))
    
    elif args.command == "add-label":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()]
        if gh.add_labels(args.issue, labels):
            print(f"✅ Added labels to {args.issue}")
        else:
            print(f"❌ Failed to add labels to {args.issue}")
            sys.exit(1)
    
    elif args.command == "remove-label":
        labels = [l.strip() for l in args.labels.split(",") if l.strip()]
        if gh.remove_labels(args.issue, labels):
            print(f"✅ Removed labels from {args.issue}")
        else:
            print(f"❌ Failed to remove labels from {args.issue}")
            sys.exit(1)


if __name__ == "__main__":
    main()
