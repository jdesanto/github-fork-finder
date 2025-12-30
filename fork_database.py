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
        self.db_dir = None  # Will be set if using directory format
        self.is_directory_format = False
        self.repos = {}  # owner/repo -> repo data
        self.forks_by_parent = {}  # parent -> list of forks
        self.parent_lookup = {}  # fork -> parent
        self._detect_and_load()

    def _detect_and_load(self):
        """Detect storage format and load accordingly."""
        # Check if db_file is a directory
        if self.db_file.is_dir():
            self.db_dir = self.db_file
            self.is_directory_format = True
            self._load_from_directory()
        # Check if it's a single file
        elif self.db_file.exists() and self.db_file.is_file():
            self.is_directory_format = False
            self._load_from_single_file()
        # Check if path with .db extension exists (directory indicator)
        elif self.db_file.with_suffix('.db').exists() and self.db_file.with_suffix('.db').is_dir():
            self.db_dir = self.db_file.with_suffix('.db')
            self.is_directory_format = True
            self._load_from_directory()
        # New database - determine format from path
        else:
            # If path ends with .json, use JSON format
            if str(self.db_file).endswith('.json'):
                self.is_directory_format = False
            # Otherwise use directory format
            else:
                self.db_dir = self.db_file if not str(self.db_file).endswith('.json') else self.db_file.with_suffix('.db')
                self.is_directory_format = True

    def _load_from_single_file(self):
        """Load database from single JSON file."""
        if self.db_file.exists():
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.repos = data.get('repos', {})
                    self._rebuild_indexes()
                    print(f"Loaded {len(self.repos)} repos from {self.db_file}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load database: {e}")
                self.repos = {}

    def _load_from_directory(self):
        """Load database from directory structure with fork families."""
        if not self.db_dir.exists():
            return

        # Walk through all subdirectories and load JSON files
        total_loaded = 0
        for subdir in self.db_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith('_'):
                continue

            for json_file in subdir.glob('*.json'):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        # Load fork families format
                        for family in data.get('fork_families', []):
                            # Add root repo
                            root = family.get('root', {})
                            if root and root.get('full_name'):
                                self.repos[root['full_name']] = root
                                total_loaded += 1

                            # Add forks
                            for fork in family.get('forks', []):
                                if fork.get('full_name'):
                                    self.repos[fork['full_name']] = fork
                                    total_loaded += 1

                        # Add orphaned forks
                        for orphan in data.get('orphaned_forks', []):
                            if orphan.get('full_name'):
                                self.repos[orphan['full_name']] = orphan
                                total_loaded += 1

                except Exception as e:
                    print(f"Warning: Could not load {json_file}: {e}")

        self._rebuild_indexes()
        print(f"Loaded {len(self.repos)} repos from {self.db_dir}")

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

    def _get_repo_name_from_full_name(self, full_name: str) -> str:
        """Extract repo name from owner/repo-name."""
        return full_name.split('/', 1)[1] if '/' in full_name else full_name

    def _sanitize_dirname(self, name: str) -> str:
        """
        Get 2-letter directory name from repo name.
        Handles special characters and edge cases.
        """
        if not name:
            return "__empty"

        if len(name) < 2:
            # Handle single-character names
            return f"_{name[0].lower()}"

        # Get first two characters
        prefix = name[:2].lower()

        # Replace special characters with underscores but keep dots and hyphens
        safe_chars = []
        for char in prefix:
            if char.isalnum():
                safe_chars.append(char)
            elif char in ('.', '-'):
                safe_chars.append(char)
            else:
                safe_chars.append('_')

        result = ''.join(safe_chars)

        # Ensure it doesn't start with a problematic character
        if result[0] in ('-',):
            result = '_' + result[1:]

        return result

    def _get_file_path_for_repo(self, full_name: str) -> Path:
        """Get the file path where a repo should be stored in directory format."""
        repo_name = self._get_repo_name_from_full_name(full_name)
        dirname = self._sanitize_dirname(repo_name)
        filename = f"{repo_name}.json"
        return self.db_dir / dirname / filename

    def save(self):
        """Save database to file (delegates to format-specific methods)."""
        if self.is_directory_format:
            self._save_to_directory()
        else:
            self._save_to_single_file()

    def _save_to_single_file(self):
        """Save database to single JSON file."""
        data = {
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'total_repos': len(self.repos),
            'total_forks': len(self.parent_lookup),
            'repos': self.repos
        }

        # Write to temporary file first, then rename (atomic operation)
        temp_file = self.db_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        temp_file.rename(self.db_file)

        print(f"Saved {len(self.repos)} repos to {self.db_file}")

    def _build_fork_families(self, repos_group: Dict) -> tuple:
        """
        Organize repos into fork families.
        Returns (fork_families, orphaned_forks)

        fork_families: List of {root: repo_data, forks: [repo_data, ...]}
        orphaned_forks: List of forks whose parent is not in this group
        """
        fork_families = []
        orphaned_forks = []
        processed = set()

        # Find all root repos (not forks)
        roots = {full_name: data for full_name, data in repos_group.items()
                 if not data.get('is_fork')}

        # Build family for each root
        for root_name, root_data in sorted(roots.items()):
            if root_name in processed:
                continue

            family = {
                'root': root_data,
                'forks': []
            }

            # Find all forks of this root
            for full_name, repo_data in repos_group.items():
                if repo_data.get('is_fork') and repo_data.get('parent') == root_name:
                    family['forks'].append(repo_data)
                    processed.add(full_name)

            fork_families.append(family)
            processed.add(root_name)

        # Handle orphaned forks (parent not in this group)
        for full_name, repo_data in repos_group.items():
            if full_name not in processed and repo_data.get('is_fork'):
                orphaned_forks.append(repo_data)
                processed.add(full_name)

        return fork_families, orphaned_forks

    def _save_to_directory(self):
        """Save database to directory structure with fork families."""
        # Create directory structure
        self.db_dir.mkdir(exist_ok=True)

        # Group repos by repo name
        repos_by_name = {}
        for full_name, repo_data in self.repos.items():
            repo_name = self._get_repo_name_from_full_name(full_name)
            if repo_name not in repos_by_name:
                repos_by_name[repo_name] = {}
            repos_by_name[repo_name][full_name] = repo_data

        # Write each group to its file
        files_written = 0
        for repo_name, repos_group in repos_by_name.items():
            # Get file path for first repo in group (all have same name)
            file_path = self._get_file_path_for_repo(list(repos_group.keys())[0])

            # Create subdirectory if needed
            file_path.parent.mkdir(exist_ok=True)

            # Organize into fork families
            fork_families, orphaned_forks = self._build_fork_families(repos_group)

            # Prepare data with fork family structure
            file_data = {
                'repo_name': repo_name,
                'last_updated': datetime.utcnow().isoformat() + 'Z',
                'total_repos': len(repos_group),
                'fork_families': fork_families,
                'orphaned_forks': orphaned_forks
            }

            # Write atomically
            temp_file = file_path.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2, sort_keys=True, ensure_ascii=False)
            temp_file.rename(file_path)
            files_written += 1

        # Write global metadata
        metadata = {
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'total_repos': len(self.repos),
            'total_forks': len(self.parent_lookup),
            'total_files': files_written,
            'unique_repo_names': len(repos_by_name)
        }

        metadata_file = self.db_dir / '_metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, sort_keys=True, ensure_ascii=False)

        print(f"Saved {len(self.repos)} repos to {self.db_dir} ({files_written} files)")

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
        Merge another database file/directory into this one.
        Automatically detects format of source database.
        Returns number of new repos added.
        """
        other_path = Path(other_db_file)

        # Detect source format
        if other_path.is_dir():
            return self._merge_from_directory(other_path)
        elif other_path.with_suffix('.db').exists() and other_path.with_suffix('.db').is_dir():
            return self._merge_from_directory(other_path.with_suffix('.db'))
        elif other_path.exists() and other_path.is_file():
            return self._merge_from_single_file(other_path)
        else:
            print(f"File/directory not found: {other_db_file}")
            return 0

    def _merge_from_single_file(self, other_db_file: Path) -> int:
        """Merge from a single-file format database."""
        with open(other_db_file, 'r', encoding='utf-8') as f:
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

    def _merge_from_directory(self, other_db_dir: Path) -> int:
        """Merge from a directory-format database."""
        added = 0

        # Walk through all subdirectories and load JSON files
        for subdir in other_db_dir.iterdir():
            if not subdir.is_dir() or subdir.name.startswith('_'):
                continue

            for json_file in subdir.glob('*.json'):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        other_repos = data.get('repos', {})

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
                except Exception as e:
                    print(f"Warning: Could not merge from {json_file}: {e}")

        self._rebuild_indexes()
        return added
