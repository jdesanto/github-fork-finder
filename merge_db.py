#!/usr/bin/env python3
"""
Merge multiple fork databases together.

This is useful when multiple contributors have built their own databases
and want to combine them into a single comprehensive database.
"""

import argparse
from pathlib import Path
from fork_database import ForkDatabase


def main():
    parser = argparse.ArgumentParser(
        description='Merge multiple fork databases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge contributor databases into main database
  python merge_db.py fork_database.json contributor1.json contributor2.json

  # Merge and create a new output file
  python merge_db.py -o merged.json db1.json db2.json db3.json

  # Merge from a directory of databases
  python merge_db.py -o merged.json databases/*.json
        """
    )

    parser.add_argument(
        'databases',
        nargs='+',
        help='Database files to merge (first one is the base)'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output file (default: update first database in place)'
    )

    args = parser.parse_args()

    # Determine base database
    if args.output:
        base_db_file = args.output
        merge_files = args.databases
    else:
        base_db_file = args.databases[0]
        merge_files = args.databases[1:]

    print(f"Base database: {base_db_file}")
    print(f"Merging {len(merge_files)} database(s)...\n")

    # Load or create base database
    base_db = ForkDatabase(base_db_file)
    initial_count = len(base_db.repos)

    # Merge each database
    total_added = 0
    for db_file in merge_files:
        if not Path(db_file).exists():
            print(f"⚠️  Skipping {db_file} (not found)")
            continue

        print(f"Merging {db_file}...")
        added = base_db.merge_from_file(db_file)
        total_added += added
        print(f"  Added {added} new repositories")

    # Save merged database
    base_db.save()

    # Print summary
    print(f"\n{'='*60}")
    print("✅ MERGE COMPLETE")
    print(f"{'='*60}")
    print(f"Initial repos:  {initial_count:,}")
    print(f"Added repos:    {total_added:,}")
    print(f"Total repos:    {len(base_db.repos):,}")
    print(f"Output:         {base_db_file}")

    stats = base_db.get_stats()
    print(f"\nDatabase now contains:")
    print(f"  Total repositories: {stats['total_repos']:,}")
    print(f"  Forks: {stats['total_forks']:,}")
    print(f"  Original repos: {stats['original_repos']:,}")
    print()


if __name__ == '__main__':
    main()
