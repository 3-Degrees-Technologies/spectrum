#!/usr/bin/env python3
"""
GitRepoHelper - Helper to locate git repository root
Supports both scenarios:
1. Git repo directly in agent folder (e.g., blue/)
2. Git repo in a subfolder (e.g., blue/git/MyProject/)
"""

import os
import sys
from pathlib import Path
from typing import Optional

class GitRepoHelper:
    """Helper class for working with git repositories in agent folders"""
    
    @staticmethod
    def find_git_root(start_path: str, max_depth: int = 5) -> Optional[str]:
        """
        Recursively search for git repository root by walking up the directory tree
        
        Args:
            start_path: Directory to start searching from
            max_depth: Maximum number of parent directories to search
            
        Returns:
            Path to git root directory, or None if not found
        """
        if max_depth <= 0:
            return None
        
        git_path = os.path.join(start_path, ".git")
        if os.path.isdir(git_path) or os.path.isfile(git_path):
            return start_path
        
        parent = os.path.dirname(start_path)
        if parent == start_path:  # Reached filesystem root
            return None
        
        return GitRepoHelper.find_git_root(parent, max_depth - 1)
    
    @staticmethod
    def get_git_root() -> Optional[str]:
        """
        Get git repository root, starting from current directory
        Searches up to 5 levels up the directory tree
        
        Returns:
            Path to git root directory, or None if not found
        """
        return GitRepoHelper.find_git_root(os.getcwd(), 5)
    
    @staticmethod
    def get_git_root_or_current() -> str:
        """
        Get git repository root or current directory if not found
        
        Returns:
            Path to git root directory, or current directory
        """
        git_root = GitRepoHelper.get_git_root()
        return git_root if git_root else os.getcwd()
    
    @staticmethod
    def is_in_git_repo() -> bool:
        """
        Check if current directory or any parent (up to 5 levels) is a git repo
        
        Returns:
            True if in a git repository, False otherwise
        """
        return GitRepoHelper.get_git_root() is not None
    
    @staticmethod
    def get_agent_folder() -> Optional[str]:
        """
        Get the agent folder (blue/red/green/black)
        This is the parent of .tools directory
        If not in .tools, searches for agent folder containing .tools
        
        Returns:
            Path to agent folder, or None if not found
        """
        current_dir = os.getcwd()
        dir_name = os.path.basename(current_dir)
        
        # If we're in .tools directory, parent is the agent folder
        if dir_name == ".tools":
            parent = os.path.dirname(current_dir)
            return parent if parent else None
        
        # If we're in an agent folder (contains .tools), use current directory
        if os.path.isdir(os.path.join(current_dir, ".tools")):
            return current_dir
        
        # Otherwise, search up for a directory containing .tools
        def find_agent_folder(path: str, depth: int) -> Optional[str]:
            if depth <= 0:
                return None
            if os.path.isdir(os.path.join(path, ".tools")):
                return path
            
            parent = os.path.dirname(path)
            if parent == path:  # Reached filesystem root
                return None
            
            return find_agent_folder(parent, depth - 1)
        
        return find_agent_folder(current_dir, 3)
    
    @staticmethod
    def resolve_working_path() -> str:
        """
        Resolve path relative to git root or agent folder
        Priority: git root > agent folder > current directory
        
        Returns:
            Best working path to use for operations
        """
        git_root = GitRepoHelper.get_git_root()
        if git_root:
            return git_root
        
        agent_folder = GitRepoHelper.get_agent_folder()
        if agent_folder:
            return agent_folder
        
        return os.getcwd()
    
    @staticmethod
    def get_relative_path_to_git_root() -> Optional[str]:
        """
        Get relative path from agent folder to git root
        
        Returns:
            Relative path string, or None if not in git repo or can't determine relationship
        """
        agent_folder = GitRepoHelper.get_agent_folder()
        git_root = GitRepoHelper.get_git_root()
        
        if not agent_folder or not git_root:
            return None
        
        if git_root.startswith(agent_folder):
            relative = os.path.relpath(git_root, agent_folder)
            return relative
        elif agent_folder == git_root:
            return "."
        else:
            return None
    
    @staticmethod
    def print_diagnostics():
        """Print diagnostic information about git repository location"""
        print("=== Git Repository Diagnostics ===")
        print(f"Current Directory: {os.getcwd()}")
        
        agent_folder = GitRepoHelper.get_agent_folder()
        if agent_folder:
            print(f"Agent Folder: {agent_folder}")
        else:
            print("Agent Folder: Not detected")
        
        git_root = GitRepoHelper.get_git_root()
        if git_root:
            print(f"Git Root: {git_root}")
            print("Is Git Repo: Yes")
        else:
            print("Git Root: Not found")
            print("Is Git Repo: No")
        
        relative_path = GitRepoHelper.get_relative_path_to_git_root()
        if relative_path:
            print(f"Relative Path (Agent→Git): {relative_path}")
        else:
            print("Relative Path: N/A")
        
        print(f"Working Path: {GitRepoHelper.resolve_working_path()}")
        print("==================================")
    
    @staticmethod
    def change_to_git_root() -> bool:
        """
        Change current working directory to git root
        
        Returns:
            True if successful, False if not in git repo
        """
        git_root = GitRepoHelper.get_git_root()
        if git_root:
            os.chdir(git_root)
            return True
        return False
    
    @staticmethod
    def change_to_working_path() -> str:
        """
        Change current working directory to the best working path
        (git root, agent folder, or current directory)
        
        Returns:
            The directory we changed to
        """
        working_path = GitRepoHelper.resolve_working_path()
        os.chdir(working_path)
        return working_path
    
    @staticmethod
    def run_git_command(args: list, cwd: Optional[str] = None) -> tuple[int, str, str]:
        """
        Run a git command in the appropriate directory
        
        Args:
            args: Git command arguments (without 'git')
            cwd: Working directory (defaults to git root or current dir)
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        import subprocess
        
        if cwd is None:
            cwd = GitRepoHelper.get_git_root_or_current()
        
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 1, "", "git command not found"


def main():
    """CLI entry point for testing and diagnostics"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Git Repository Helper")
    parser.add_argument("--diagnostics", action="store_true", help="Print diagnostic information")
    parser.add_argument("--git-root", action="store_true", help="Print git root path")
    parser.add_argument("--agent-folder", action="store_true", help="Print agent folder path")
    parser.add_argument("--working-path", action="store_true", help="Print working path")
    parser.add_argument("--is-git-repo", action="store_true", help="Check if in git repository")
    parser.add_argument("--relative-path", action="store_true", help="Print relative path to git root")
    
    args = parser.parse_args()
    
    if args.diagnostics:
        GitRepoHelper.print_diagnostics()
    elif args.git_root:
        git_root = GitRepoHelper.get_git_root()
        if git_root:
            print(git_root)
        else:
            print("Not in a git repository", file=sys.stderr)
            sys.exit(1)
    elif args.agent_folder:
        agent_folder = GitRepoHelper.get_agent_folder()
        if agent_folder:
            print(agent_folder)
        else:
            print("Not in an agent folder", file=sys.stderr)
            sys.exit(1)
    elif args.working_path:
        print(GitRepoHelper.resolve_working_path())
    elif args.is_git_repo:
        if GitRepoHelper.is_in_git_repo():
            print("Yes")
            sys.exit(0)
        else:
            print("No")
            sys.exit(1)
    elif args.relative_path:
        relative = GitRepoHelper.get_relative_path_to_git_root()
        if relative:
            print(relative)
        else:
            print("N/A", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
