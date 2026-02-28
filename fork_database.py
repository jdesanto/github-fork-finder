#!/usr/bin/env python3
"""
Fork Database - owner-organized JSON files with a slim fork-relationship schema.

Directory layout (committed to git):
  fork-db/
    _metadata.json          ← counts, last-updated, format marker
    ce/celestiaorg.json     ← all repos crawled for owner "celestiaorg"
    01/01node.json          ← all repos crawled for owner "01node"
    ...

Each owner file:
  {
    "owner": "celestiaorg",
    "updated_at": "2025-12-30T09:17Z",
    "repos": [
      { "full_name": "celestiaorg/celestia-node", "is_fork": false,
        "parent": null, "source": null, "stars": 1234,
        "language": "Go", "last_checked": "2025-12-30T09:17Z" },
      ...
    ]
  }

For cross-owner queries, build a side-by-side SQLite index:
  python3 build_index.py      →  fork-db.sqlite  (not committed)
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class ForkDatabase:
    def __init__(self, db_path: str = "fork-db/"):
        self.db_path = Path(db_path)
        self.repos: Dict[str, Dict] = {}       # full_name -> slim entry
        self.forks_by_parent: Dict[str, List[str]] = {}
        self.parent_lookup: Dict[str, str] = {}
        self._dirty_owners: set = set()        # owners needing a file write
        self.is_directory_format: bool = True  # single-file JSON if False
        self._detect_and_load()

    # ------------------------------------------------------------------
    # Detection & loading
    # ------------------------------------------------------------------

    def _detect_and_load(self):
        p = self.db_path
        if p.is_dir():
            self.is_directory_format = True
            meta_path = p / '_metadata.json'
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta.get('format') == 'owner-v1':
                        self._load_owner_directory()
                        return
                except Exception:
                    pass
            # Old fork_families format — still readable (needed pre-migration)
            self._load_old_directory()
        elif p.exists() and p.is_file():
            self.is_directory_format = False
            self._load_single_file()
        else:
            # New empty database — format inferred from path
            self.is_directory_format = not str(p).endswith('.json')

    def _load_owner_directory(self):
        """Load new owner-organized format (format: owner-v1)."""
        total = 0
        for subdir in self.db_path.iterdir():
            if not subdir.is_dir() or subdir.name.startswith('_'):
                continue
            for jf in subdir.glob('*.json'):
                try:
                    data = json.loads(jf.read_text(encoding='utf-8'))
                    for entry in data.get('repos', []):
                        if entry.get('full_name'):
                            self.repos[entry['full_name']] = entry
                            total += 1
                except Exception as e:
                    print(f"Warning: could not load {jf}: {e}")
        self._rebuild_indexes()
        print(f"Loaded {total} repos from {self.db_path}")

    def _load_old_directory(self):
        """Load old fork_families/orphaned_forks format (pre-migration compat)."""
        total = 0
        for subdir in self.db_path.iterdir():
            if not subdir.is_dir() or subdir.name.startswith('_'):
                continue
            for jf in subdir.glob('*.json'):
                try:
                    data = json.loads(jf.read_text(encoding='utf-8'))
                    entries = []
                    for family in data.get('fork_families', []):
                        root = family.get('root')
                        if root and root.get('full_name'):
                            entries.append(root)
                        for fork in family.get('forks', []):
                            if fork.get('full_name'):
                                entries.append(fork)
                    for orphan in data.get('orphaned_forks', []):
                        if orphan.get('full_name'):
                            entries.append(orphan)
                    for entry in entries:
                        slim = _slim(entry)
                        self.repos[slim['full_name']] = slim
                        total += 1
                except Exception as e:
                    print(f"Warning: could not load {jf}: {e}")
        self._rebuild_indexes()
        print(f"Loaded {total} repos from {self.db_path} (old format)")

    def _load_single_file(self):
        """Load single-file JSON format (has top-level 'repos' dict)."""
        try:
            data = json.loads(self.db_path.read_text(encoding='utf-8'))
            for full_name, entry in data.get('repos', {}).items():
                self.repos[full_name] = _slim(entry)
            self._rebuild_indexes()
            print(f"Loaded {len(self.repos)} repos from {self.db_path}")
        except Exception as e:
            print(f"Warning: could not load {self.db_path}: {e}")

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save(self):
        """Persist all dirty changes to disk."""
        if self.is_directory_format:
            self._save_owner_directory()
        else:
            self._save_single_file()

    def _save_owner_directory(self):
        self.db_path.mkdir(exist_ok=True)

        # Group all in-memory repos by lowercase owner name.
        # GitHub usernames are case-insensitive; lowercasing avoids overwrite
        # collisions on case-insensitive filesystems (e.g. macOS default HFS+).
        by_owner: Dict[str, List[Dict]] = {}
        for full_name, entry in self.repos.items():
            owner = full_name.split('/')[0].lower()
            by_owner.setdefault(owner, []).append(entry)

        # Write only dirty owners; if nothing marked dirty write everything
        targets = self._dirty_owners if self._dirty_owners else set(by_owner)

        files_written = 0
        for owner in sorted(targets):
            if owner not in by_owner:
                continue
            file_path = self._get_file_path_for_owner(owner)
            file_path.parent.mkdir(exist_ok=True)
            file_data = {
                'owner': owner,
                'updated_at': _utcnow(),
                'repos': sorted(by_owner[owner], key=lambda r: r['full_name']),
            }
            tmp = file_path.with_suffix('.tmp')
            tmp.write_text(
                json.dumps(file_data, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
            tmp.rename(file_path)
            files_written += 1

        # Update metadata
        meta = {
            'format': 'owner-v1',
            'updated_at': _utcnow(),
            'total_repos': len(self.repos),
            'total_forks': len(self.parent_lookup),
            'total_owners': len(by_owner),
        }
        (self.db_path / '_metadata.json').write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding='utf-8'
        )

        self._dirty_owners.clear()
        print(f"Saved {len(self.repos)} repos to {self.db_path} ({files_written} files written)")

    def _save_single_file(self):
        data = {
            'updated_at': _utcnow(),
            'total_repos': len(self.repos),
            'total_forks': len(self.parent_lookup),
            'repos': dict(sorted(self.repos.items())),
        }
        tmp = self.db_path.with_suffix('.tmp')
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        tmp.rename(self.db_path)
        print(f"Saved {len(self.repos)} repos to {self.db_path}")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _get_file_path_for_owner(self, owner: str) -> Path:
        owner_lower = owner.lower()
        prefix = _owner_prefix(owner_lower)
        return self.db_path / prefix / f"{owner_lower}.json"

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def has_repo(self, full_name: str) -> bool:
        return full_name in self.repos

    def get_repo(self, full_name: str) -> Optional[Dict]:
        return self.repos.get(full_name)

    def add_repo(self, full_name: str, repo_data: Dict):
        """Add/update using a raw GitHub API response dict. Stamps last_checked."""
        is_fork = repo_data.get('fork', False)
        parent_info = repo_data.get('parent') or {}
        source_info = repo_data.get('source') or {}

        entry = {
            'full_name': full_name,
            'is_fork': is_fork,
            'parent': parent_info.get('full_name') if is_fork else None,
            'source': source_info.get('full_name') if is_fork else None,
            'stars': repo_data.get('stargazers_count', repo_data.get('stars', 0)),
            'language': repo_data.get('language'),
            'last_checked': _utcnow(),
        }
        self.repos[full_name] = entry
        self._update_indexes(full_name, entry)
        self._dirty_owners.add(full_name.split('/')[0].lower())

    def add_repo_entry(self, entry: Dict):
        """Add/update using a pre-processed slim entry. Preserves last_checked."""
        if not entry or not entry.get('full_name'):
            return
        slim = _slim(entry)
        self.repos[slim['full_name']] = slim
        self._update_indexes(slim['full_name'], slim)
        self._dirty_owners.add(slim['full_name'].split('/')[0].lower())

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    def _update_indexes(self, full_name: str, entry: Dict):
        if entry.get('is_fork') and entry.get('parent'):
            parent = entry['parent']
            forks = self.forks_by_parent.setdefault(parent, [])
            if full_name not in forks:
                forks.append(full_name)
            self.parent_lookup[full_name] = parent

    def _rebuild_indexes(self):
        """Rebuild fork-relationship indexes from self.repos."""
        self.forks_by_parent = {}
        self.parent_lookup = {}
        for full_name, entry in self.repos.items():
            self._update_indexes(full_name, entry)

    # ------------------------------------------------------------------
    # Relationship queries
    # ------------------------------------------------------------------

    def get_parent(self, fork_name: str) -> Optional[str]:
        return self.parent_lookup.get(fork_name)

    def get_forks(self, parent_name: str) -> List[str]:
        return self.forks_by_parent.get(parent_name, [])

    def get_fork_chain(self, repo_name: str) -> List[str]:
        """Walk parent links from repo_name to the ultimate source."""
        chain = [repo_name]
        seen = {repo_name}
        current = repo_name
        while current in self.parent_lookup:
            parent = self.parent_lookup[current]
            if parent in seen:
                break
            chain.append(parent)
            seen.add(parent)
            current = parent
        return chain

    def get_missing_repos(self, full_names: List[str]) -> List[str]:
        return [n for n in full_names if n not in self.repos]

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------

    def get_owner_repos(self, owner: str) -> List[Dict]:
        """Return all repos for a given owner (fast in-memory lookup)."""
        owner_lower = owner.lower()
        return [
            entry for full_name, entry in self.repos.items()
            if full_name.split('/')[0].lower() == owner_lower
        ]

    # ------------------------------------------------------------------
    # Search & stats
    # ------------------------------------------------------------------

    def search_by_name(self, name: str) -> List[str]:
        """Case-insensitive substring search on the repo name (part after '/')."""
        name_lower = name.lower()
        return [
            fn for fn in self.repos
            if name_lower in fn.split('/', 1)[-1].lower()
        ]

    def get_stats(self) -> Dict:
        total_repos = len(self.repos)
        total_forks = len(self.parent_lookup)
        total_parents = len(self.forks_by_parent)
        fork_counts = {p: len(f) for p, f in self.forks_by_parent.items()}
        top_forked = sorted(fork_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            'total_repos':    total_repos,
            'total_forks':    total_forks,
            'total_parents':  total_parents,
            'original_repos': total_repos - total_forks,
            'top_forked':     top_forked,
        }

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------

    def export_fork_relationships(self) -> List[Dict]:
        """Export fork relationships in a flat list format."""
        relationships = []
        for fork_name, parent_name in self.parent_lookup.items():
            fork_data = self.repos.get(fork_name)
            parent_data = self.repos.get(parent_name)
            if not fork_data or not parent_data:
                continue
            source_name = fork_data.get('source') or parent_name
            source_data = self.repos.get(source_name) or parent_data
            relationships.append({
                'fork':           fork_name,
                'fork_url':       f"https://github.com/{fork_name}",
                'parent':         parent_name,
                'parent_url':     f"https://github.com/{parent_name}",
                'source':         source_name,
                'source_url':     f"https://github.com/{source_name}",
                'fork_stars':     fork_data.get('stars', 0),
                'parent_stars':   parent_data.get('stars', 0),
            })
        return relationships

    def export_simple(self) -> List[Dict]:
        """Export [{"url": ..., "parent_url": ... or null}, ...] format."""
        return [
            {
                'url': f"https://github.com/{fn}",
                'parent_url': (
                    f"https://github.com/{entry['parent']}"
                    if entry.get('parent') else None
                ),
            }
            for fn, entry in sorted(self.repos.items())
        ]

    # ------------------------------------------------------------------
    # SQLite index builder
    # ------------------------------------------------------------------

    def build_sqlite_index(self, out_path: str = 'fork-db.sqlite'):
        """Write a SQLite query index from all in-memory repos."""
        out = Path(out_path)
        if out.exists():
            out.unlink()

        conn = sqlite3.connect(str(out))
        conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE repos (
                full_name    TEXT PRIMARY KEY,
                owner        TEXT NOT NULL,
                is_fork      INTEGER NOT NULL DEFAULT 0,
                parent       TEXT,
                source       TEXT,
                stars        INTEGER DEFAULT 0,
                language     TEXT,
                last_checked TEXT
            );
            CREATE INDEX idx_owner  ON repos(owner);
            CREATE INDEX idx_parent ON repos(parent);
            CREATE INDEX idx_lang   ON repos(language);
        """)

        rows = [
            (
                fn,
                fn.split('/')[0],
                1 if entry.get('is_fork') else 0,
                entry.get('parent'),
                entry.get('source'),
                entry.get('stars', 0),
                entry.get('language'),
                entry.get('last_checked'),
            )
            for fn, entry in self.repos.items()
        ]
        conn.executemany(
            "INSERT INTO repos VALUES (?,?,?,?,?,?,?,?)", rows
        )
        conn.commit()
        conn.close()
        print(f"Built SQLite index: {out} ({len(rows)} repos)")

    # ------------------------------------------------------------------
    # Merge / import
    # ------------------------------------------------------------------

    def merge_from_file(self, other_path: str) -> int:
        """
        Merge another database into this one.
        Handles: new owner-v1 dir, old fork_families dir, single-file JSON.
        Returns number of newly added repos.
        """
        path = Path(other_path)
        if not path.exists():
            print(f"Not found: {other_path}")
            return 0

        if path.is_dir():
            meta_path = path / '_metadata.json'
            fmt = ''
            if meta_path.exists():
                try:
                    fmt = json.loads(meta_path.read_text()).get('format', '')
                except Exception:
                    pass
            if fmt == 'owner-v1':
                return self._merge_owner_directory(path)
            else:
                return self._merge_old_directory(path)
        else:
            return self._merge_json_file(path)

    def _merge_entries(self, entries: List[Dict]) -> int:
        added = 0
        for entry in entries:
            full_name = entry.get('full_name')
            if not full_name:
                continue
            existing = self.repos.get(full_name)
            if existing is None:
                self.add_repo_entry(entry)
                added += 1
            elif (entry.get('last_checked') or '') > (existing.get('last_checked') or ''):
                self.add_repo_entry(entry)
        return added

    def _merge_owner_directory(self, path: Path) -> int:
        added = 0
        for subdir in sorted(path.iterdir()):
            if not subdir.is_dir() or subdir.name.startswith('_'):
                continue
            for jf in subdir.glob('*.json'):
                try:
                    data = json.loads(jf.read_text(encoding='utf-8'))
                    added += self._merge_entries(data.get('repos', []))
                except Exception as e:
                    print(f"Warning: could not merge {jf}: {e}")
        return added

    def _merge_old_directory(self, path: Path) -> int:
        """Merge old fork_families/orphaned_forks directory format."""
        added = 0
        for subdir in sorted(path.iterdir()):
            if not subdir.is_dir() or subdir.name.startswith('_'):
                continue
            for jf in subdir.glob('*.json'):
                try:
                    data = json.loads(jf.read_text(encoding='utf-8'))
                    entries = []
                    for family in data.get('fork_families', []):
                        root = family.get('root')
                        if root and root.get('full_name'):
                            entries.append(_slim(root))
                        for fork in family.get('forks', []):
                            if fork.get('full_name'):
                                entries.append(_slim(fork))
                    for orphan in data.get('orphaned_forks', []):
                        if orphan.get('full_name'):
                            entries.append(_slim(orphan))
                    added += self._merge_entries(entries)
                except Exception as e:
                    print(f"Warning: could not merge {jf}: {e}")
        return added

    def _merge_json_file(self, path: Path) -> int:
        """Merge single-file JSON (top-level 'repos' dict or list)."""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return 0

        repos_raw = data.get('repos', {})
        if isinstance(repos_raw, dict):
            entries = [_slim(v) for v in repos_raw.values()]
        elif isinstance(repos_raw, list):
            entries = [_slim(e) for e in repos_raw]
        else:
            entries = []
        return self._merge_entries(entries)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _owner_prefix(owner: str) -> str:
    """Return the 2-char directory prefix for an owner name."""
    if not owner:
        return '__'
    prefix = owner[:2].lower()
    safe = []
    for ch in prefix:
        if ch.isalnum():
            safe.append(ch)
        elif ch == '-':
            safe.append('_')  # leading hyphen is invalid; map to underscore
        else:
            safe.append('_')
    result = ''.join(safe)
    return result if result else '__'


def _slim(entry: Dict) -> Dict:
    """
    Normalize any entry dict to the slim schema.
    Accepts both the old fat schema (html_url, description, etc.)
    and the new slim schema.
    """
    full_name = entry.get('full_name', '')
    return {
        'full_name':   full_name,
        'is_fork':     bool(entry.get('is_fork', False)),
        'parent':      entry.get('parent'),
        'source':      entry.get('source'),
        'stars':       entry.get('stars', 0),
        'language':    entry.get('language'),
        'last_checked': entry.get('last_checked'),
    }
