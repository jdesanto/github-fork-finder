#!/usr/bin/env python3
"""
Fork Database - Manages a database of GitHub repositories and their fork relationships.

The database is designed to be:
- Additive: New data is merged with existing data
- Collaborative: Multiple contributors can add entries
- Efficient: Checks database before making API calls
- Queryable: Easy to find parents, forks, and relationships
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime


class ForkDatabase:
    def __init__(self, db_file: str = "fork_database.json"):
        self.db_file = Path(db_file)
        self.repos = {}  # owner/repo -> repo data
        self.forks_by_parent = {}  # parent -> list of forks
        self.parent_lookup = {}  # fork -> parent
        self._load()

    def _load(self):
        """Load database from file."""
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.repos = data.get('repos', {})
                    self._rebuild_indexes()
                    print(f"Loaded {len(self.repos)} repos from database")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load database: {e}")
                self.repos = {}

    def _rebuild_indexes(self):
        """Rebuild lookup indexes from repo data."""
        self.forks_by_parent = {}
        self.parent_lookup = {}

        for full_name, repo in self.repos.items():
            if repo.get('is_fork') and repo.get('parent'):
                parent = repo['parent']
                if parent not in self.forks_by_parent:
                    self.forks_by_parent[parent] = []
                self.forks_by_parent[parent].append(full_name)
                self.parent_lookup[full_name] = parent

    def save(self):
        """Save database to file."""
        data = {
            'version': '1.0',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'total_repos': len(self.repos),
            'total_forks': len(self.parent_lookup),
            'repos': self.repos
        }

        # Write to temporary file first, then rename (atomic operation)
        temp_file = self.db_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        temp_file.rename(self.db_file)

        print(f"Saved {len(self.repos)} repos to database")

    def has_repo(self, full_name: str) -> bool:
        """Check if repository is already in database."""
        return full_name in self.repos

    def get_repo(self, full_name: str) -> Optional[Dict]:
        """Get repository data from database."""
        return self.repos.get(full_name)

    def add_repo(self, full_name: str, repo_data: Dict):
        """
        Add or update repository in database.

        Args:
            full_name: Repository full name (owner/repo)
            repo_data: Repository data from GitHub API
        """
        # Extract relevant fields
        is_fork = repo_data.get('fork', False)
        parent_info = repo_data.get('parent', {})
        source_info = repo_data.get('source', {})

        entry = {
            'full_name': full_name,
            'name': repo_data.get('name'),
            'owner': repo_data.get('owner', {}).get('login'),
            'is_fork': is_fork,
            'parent': parent_info.get('full_name') if is_fork else None,
            'source': source_info.get('full_name') if is_fork else None,
            'html_url': repo_data.get('html_url'),
            'description': repo_data.get('description'),
            'stars': repo_data.get('stargazers_count', 0),
            'forks_count': repo_data.get('forks_count', 0),
            'language': repo_data.get('language'),
            'created_at': repo_data.get('created_at'),
            'updated_at': repo_data.get('updated_at'),
            'last_checked': datetime.utcnow().isoformat() + 'Z'
        }

        self.repos[full_name] = entry

        # Update indexes
        if is_fork and entry['parent']:
            parent = entry['parent']
            if parent not in self.forks_by_parent:
                self.forks_by_parent[parent] = []
            if full_name not in self.forks_by_parent[parent]:
                self.forks_by_parent[parent].append(full_name)
            self.parent_lookup[full_name] = parent

    def get_parent(self, fork_name: str) -> Optional[str]:
        """Get the parent repository of a fork."""
        return self.parent_lookup.get(fork_name)

    def get_forks(self, parent_name: str) -> List[str]:
        """Get all forks of a repository."""
        return self.forks_by_parent.get(parent_name, [])

    def get_fork_chain(self, repo_name: str) -> List[str]:
        """
        Get the full fork chain from a repository to its source.
        Returns [repo, parent, grandparent, ..., source]
        """
        chain = [repo_name]
        current = repo_name

        # Prevent infinite loops
        seen = {repo_name}

        while current in self.parent_lookup:
            parent = self.parent_lookup[current]
            if parent in seen:
                break
            chain.append(parent)
            seen.add(parent)
            current = parent

        return chain

    def get_missing_repos(self, full_names: List[str]) -> List[str]:
        """Get list of repositories not yet in database."""
        return [name for name in full_names if name not in self.repos]

    def export_fork_relationships(self) -> List[Dict]:
        """
        Export fork relationships in the old format for compatibility.
        """
        relationships = []

        for fork_name, parent_name in self.parent_lookup.items():
            fork_data = self.repos.get(fork_name)
            parent_data = self.repos.get(parent_name)

            if fork_data and parent_data:
                source_name = fork_data.get('source') or parent_name
                source_data = self.repos.get(source_name) or parent_data

                relationships.append({
                    'fork': fork_name,
                    'fork_url': fork_data['html_url'],
                    'parent': parent_name,
                    'parent_url': parent_data['html_url'],
                    'source': source_name,
                    'source_url': source_data['html_url'],
                    'fork_stars': fork_data['stars'],
                    'parent_stars': parent_data['stars'],
                    'fork_updated': fork_data['updated_at'],
                    'parent_updated': parent_data['updated_at']
                })

        return relationships

    def get_stats(self) -> Dict:
        """Get database statistics."""
        total_repos = len(self.repos)
        total_forks = len(self.parent_lookup)
        total_parents = len(self.forks_by_parent)

        # Find most forked repos
        fork_counts = {parent: len(forks) for parent, forks in self.forks_by_parent.items()}
        top_forked = sorted(fork_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'total_repos': total_repos,
            'total_forks': total_forks,
            'total_parents': total_parents,
            'original_repos': total_repos - total_forks,
            'top_forked': top_forked
        }

    def search_by_name(self, name: str) -> List[str]:
        """Search for repositories by name (case-insensitive)."""
        name_lower = name.lower()
        return [
            full_name for full_name, repo in self.repos.items()
            if name_lower in repo.get('name', '').lower()
        ]

    def merge_from_file(self, other_db_file: str) -> int:
        """
        Merge another database file into this one.
        Returns number of new repos added.
        """
        if not Path(other_db_file).exists():
            print(f"File not found: {other_db_file}")
            return 0

        with open(other_db_file, 'r') as f:
            data = json.load(f)
            other_repos = data.get('repos', {})

        added = 0
        for full_name, repo_data in other_repos.items():
            if full_name not in self.repos:
                self.repos[full_name] = repo_data
                added += 1
            else:
                # Update if other data is newer
                existing_checked = self.repos[full_name].get('last_checked', '')
                other_checked = repo_data.get('last_checked', '')
                if other_checked > existing_checked:
                    self.repos[full_name] = repo_data

        self._rebuild_indexes()
        return added
