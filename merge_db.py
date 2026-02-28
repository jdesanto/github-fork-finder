#!/usr/bin/env python3
"""
Merge one or more result files into the master fork database.

Accepts any combination of:
  - Single-file JSON results (output of find_forks.py)
  - Owner-organized directories (owner-v1 format)
  - Old fork_families directories (pre-migration format)

Usage:
  python3 merge_db.py fork-db/ results.json
  python3 merge_db.py fork-db/ results1.json results2.json
  python3 merge_db.py -o merged/ db1/ db2/ results.json
"""

import argparse
from pathlib import Path
from fork_database import ForkDatabase


def main():
    parser = argparse.ArgumentParser(
        description='Merge one or more databases/result files into a master database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 merge_db.py fork-db/ github_links_results.json
  python3 merge_db.py fork-db/ results1.json results2.json
  python3 merge_db.py -o merged/ old_db/ contrib1.json contrib2.json
        """,
    )
    parser.add_argument('databases', nargs='+',
                        help='Database files/directories to merge (first = base when no -o)')
    parser.add_argument('-o', '--output',
                        help='Output path (default: update first database in place)')
    args = parser.parse_args()

    if args.output:
        base_path = args.output
        merge_files = args.databases
    else:
        base_path = args.databases[0]
        merge_files = args.databases[1:]

    if not merge_files:
        print("Nothing to merge.")
        return

    print(f"Base database: {base_path}")
    print(f"Merging {len(merge_files)} source(s)...\n")

    base_db = ForkDatabase(base_path)
    initial_count = len(base_db.repos)

    total_added = 0
    for source in merge_files:
        if not Path(source).exists():
            print(f"  Skipping {source} (not found)")
            continue
        print(f"Merging {source}...")
        added = base_db.merge_from_file(source)
        total_added += added
        print(f"  Added {added} new repositories")

    base_db.save()

    print(f"\n{'='*60}")
    print("MERGE COMPLETE")
    print(f"{'='*60}")
    print(f"Initial repos:  {initial_count:,}")
    print(f"Added repos:    {total_added:,}")
    print(f"Total repos:    {len(base_db.repos):,}")
    print(f"Output:         {base_path}")

    stats = base_db.get_stats()
    print(f"\nDatabase now contains:")
    print(f"  Total repositories: {stats['total_repos']:,}")
    print(f"  Forks:              {stats['total_forks']:,}")
    print(f"  Original repos:     {stats['original_repos']:,}")
    print()


if __name__ == '__main__':
    main()
