"""
SQLite index builder — used by db.py index.
"""

import sys
from pathlib import Path

from .fork_database import ForkDatabase


def build(db_path: str, out_path: str, rebuild: bool = False) -> int:
    out = Path(out_path)

    if out.exists():
        if rebuild:
            print(f"Removing existing index: {out}")
            out.unlink()
        else:
            print(f"Index already exists: {out}")
            print("Use --rebuild to drop and recreate it.")
            return 1

    print(f"Loading database: {db_path}")
    db = ForkDatabase(db_path)
    total = len(db.repos)

    if total == 0:
        print("Database is empty — nothing to index.")
        return 0

    print(f"Building index for {total} repos...")
    db.build_sqlite_index(out_path)

    stats = db.get_stats()
    print(f"\nIndex stats:")
    print(f"  Total repos:    {stats['total_repos']:,}")
    print(f"  Forks:          {stats['total_forks']:,}")
    print(f"  Original repos: {stats['original_repos']:,}")
    print(f"\nIndex written to: {out}")
    print("Query with: python3 db.py query --top 20")
    return 0
