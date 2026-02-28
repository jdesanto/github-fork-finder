#!/usr/bin/env python3
"""
Build (or rebuild) the side-by-side SQLite query index from the JSON source files.

The SQLite index is NOT committed to git — it is regenerated on demand.
It enables fast cross-owner queries: top forked repos, language filters,
fork-chain traversal without loading every JSON file.

Usage:
  python3 build_index.py                        # fork-db/ → fork-db.sqlite
  python3 build_index.py --db fork-db/ --out query.sqlite
  python3 build_index.py --rebuild              # delete and recreate
"""

import argparse
import sys
from pathlib import Path

from fork_database import ForkDatabase


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
    print("Query with: python3 query_db.py --db fork-db/ --top 20")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Build a SQLite query index from the fork-db/ JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 build_index.py
  python3 build_index.py --db fork-db/ --out fork-db.sqlite
  python3 build_index.py --rebuild
        """,
    )
    parser.add_argument('--db', default='fork-db/',
                        help='Source database directory (default: fork-db/)')
    parser.add_argument('--out', default='fork-db.sqlite',
                        help='Output SQLite file (default: fork-db.sqlite)')
    parser.add_argument('--rebuild', action='store_true',
                        help='Delete existing index and recreate it')
    args = parser.parse_args()
    sys.exit(build(args.db, args.out, rebuild=args.rebuild))


if __name__ == '__main__':
    main()
