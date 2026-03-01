#!/usr/bin/env python3
"""
One-time migration: convert fork-db/ from the old repo-name-organized layout
to the new owner-organized layout.

Old layout:  fork-db/ab/some-repo.json   (keyed on first 2 chars of repo name)
New layout:  fork-db/ce/celestiaorg.json  (keyed on first 2 chars of owner name)

Usage (run from project root):
  python3 -m lib.migrate_db fork-db/ fork-db-new/
  python3 -m lib.migrate_db fork-db/ fork-db-new/ --verify
"""

import argparse
import sys
from pathlib import Path

from .fork_database import ForkDatabase


def migrate(source_dir: str, dest_dir: str, verify: bool = False) -> int:
    source = Path(source_dir)
    dest = Path(dest_dir)

    if not source.exists():
        print(f"Error: source directory does not exist: {source}")
        return 1

    if dest.exists() and any(dest.iterdir()):
        print(f"Error: destination already exists and is non-empty: {dest}")
        print("Remove it first or choose a different destination.")
        return 1

    print(f"Loading source database: {source}")
    src_db = ForkDatabase(str(source))
    src_count = len(src_db.repos)
    print(f"Loaded {src_count} repos")

    if src_count == 0:
        print("Source database is empty — nothing to migrate.")
        return 0

    print(f"\nWriting new owner-organized layout to: {dest}")
    dest_db = ForkDatabase(str(dest))
    for full_name, entry in src_db.repos.items():
        dest_db.add_repo_entry(entry)
    dest_db.save()

    dest_count = len(dest_db.repos)
    print(f"Wrote {dest_count} repos")

    if verify:
        print("\nVerifying counts...")
        if src_count == dest_count:
            print(f"OK: {src_count} repos in both source and destination")
        else:
            print(f"WARNING: source={src_count}, destination={dest_count} — counts differ!")
            missing = set(src_db.repos) - set(dest_db.repos)
            if missing:
                print(f"  Missing from destination ({min(10, len(missing))} shown):")
                for fn in sorted(missing)[:10]:
                    print(f"    {fn}")
            return 1

    print("\nMigration complete.")
    print(f"Next steps:")
    print(f"  mv {source} {source}-old")
    print(f"  mv {dest} {source}")
    print(f"  python3 db.py index")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Migrate fork-db/ from old layout to owner-organized layout',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m lib.migrate_db fork-db/ fork-db-new/
  python3 -m lib.migrate_db fork-db/ fork-db-new/ --verify
        """,
    )
    parser.add_argument('source', help='Source directory (old layout)')
    parser.add_argument('dest', help='Destination directory (new layout)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify that all source repos appear in destination')
    args = parser.parse_args()
    sys.exit(migrate(args.source, args.dest, verify=args.verify))


if __name__ == '__main__':
    main()
