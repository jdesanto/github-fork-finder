#!/usr/bin/env python3
"""
Unified entry point for fork database operations.

  python3 db.py export --csv forks.csv       # export fork relationships for analysis
  python3 db.py merge results.json           # merge fetched results into fork-db/
  python3 db.py enrich                       # fetch missing parent repos
  python3 db.py query --owner celestiaorg    # query fork relationships
  python3 db.py validate --sample 200        # spot-check against live GitHub data
  python3 db.py index [--rebuild]            # build SQLite query index
"""

import argparse
import sys
from pathlib import Path


# ------------------------------------------------------------------
# export
# ------------------------------------------------------------------

def cmd_export(args):
    from lib.export_db import export

    if not args.csv and not args.json and not args.simple and not args.index:
        print("Specify at least one output: --csv, --json, --simple, or --index FILE")
        print("Use --help for details.")
        return

    export(
        db_path=args.db,
        csv_path=args.csv,
        json_path=args.json,
        simple_path=args.simple,
        index_path=args.index,
    )


# ------------------------------------------------------------------
# merge
# ------------------------------------------------------------------

def cmd_merge(args):
    from lib.fork_database import ForkDatabase

    base_db = ForkDatabase(args.db)
    initial = len(base_db.repos)
    total_added = 0

    for source in args.sources:
        if not Path(source).exists():
            print(f"  Skipping {source} (not found)")
            continue
        print(f"Merging {source}...")
        added = base_db.merge_from_file(source)
        total_added += added
        print(f"  +{added} repos")

    base_db.save()

    stats = base_db.get_stats()
    print(f"\nDone: {initial:,} → {len(base_db.repos):,} repos (+{total_added:,})")
    print(f"Forks: {stats['total_forks']:,}   Originals: {stats['original_repos']:,}")
    print(f"Saved to: {args.db}")


# ------------------------------------------------------------------
# query
# ------------------------------------------------------------------

def cmd_query(args):
    from lib.fork_database import ForkDatabase
    from lib.query_db import (
        print_repo_info, print_owner_repos, find_parent,
        search_repos, list_top_forked, show_stats, show_random_fork_example,
    )

    db = ForkDatabase(args.db)

    if args.info:
        print_repo_info(db, args.info)
    elif args.owner:
        print_owner_repos(db, args.owner)
    elif args.parent:
        find_parent(db, args.parent)
    elif args.search:
        search_repos(db, args.search)
    elif args.top:
        list_top_forked(db, args.top)
    elif args.stats:
        show_stats(db)
    elif args.random:
        show_random_fork_example(db)
    else:
        print("Specify a query option. Use `python3 db.py query --help` to see all options.")


# ------------------------------------------------------------------
# validate
# ------------------------------------------------------------------

def cmd_validate(args):
    import random
    from lib.fork_database import ForkDatabase, _utcnow
    from lib.github_api import load_token, prompt_for_token, GitHubAPIClient
    from lib.validate_db import check_repo, print_report

    token = args.token or load_token()
    if not token and sys.stdin.isatty():
        token = prompt_for_token()
    if not token:
        print("Warning: No GitHub token. Rate limit is 60 req/hour.")

    print(f"Loading database: {args.db}")
    db = ForkDatabase(args.db)
    total_db = len(db.repos)
    print(f"Loaded {total_db:,} repos")

    if total_db == 0:
        print("Database is empty.")
        return

    if args.owner:
        candidates = [fn for fn in db.repos if fn.split('/')[0].lower() == args.owner.lower()]
        if not candidates:
            print(f"No repos found for owner '{args.owner}'")
            return
        sample = candidates
        print(f"Checking {len(sample)} repos for owner '{args.owner}'...")
    elif getattr(args, 'full', False):
        sample = list(db.repos.keys())
        print(f"Checking all {len(sample):,} repos...")
    else:
        n = min(args.sample, total_db)
        sample = random.sample(list(db.repos.keys()), n)
        print(f"Checking {n:,} random repos from {total_db:,} total...")

    client = GitHubAPIClient(token=token, delay=args.delay)
    results = {'ok': [], 'changed': [], 'deleted': []}

    for i, full_name in enumerate(sample, 1):
        if i % 50 == 0 or i == len(sample):
            print(f"  {i}/{len(sample)} ({100*i/len(sample):.0f}%) — "
                  f"{client.api_calls_made} API calls")

        stored = db.get_repo(full_name)
        result = check_repo(client, stored)
        bucket = result['status'] if result['status'] in ('deleted', 'ok') else 'changed'
        results[bucket].append(result)

        if result['status'] != 'ok':
            icon = 'x' if result['status'] == 'deleted' else '!'
            print(f"  [{icon}] {full_name}: {result['status']}")
            for change in result['changes']:
                print(f"      {change}")

    print_report(results, len(sample))
    print(f"API calls made: {client.api_calls_made:,}")

    total_issues = len(results['changed']) + len(results['deleted'])

    if total_issues > 0 and not args.fix:
        print(f"\nRun with --fix to update {total_issues} "
              f"stale entr{'y' if total_issues == 1 else 'ies'}.")
        return

    if args.fix and total_issues > 0:
        print(f"\nFixing {total_issues} entr{'y' if total_issues == 1 else 'ies'}...")
        fixed = 0
        for result in results['changed']:
            if result['live_data']:
                db.add_repo(result['full_name'], result['live_data'])
                fixed += 1
        for result in results['deleted']:
            stored = db.get_repo(result['full_name'])
            if stored:
                stored['last_checked'] = _utcnow()
                stored['deleted'] = True
                db.add_repo_entry(stored)
                fixed += 1
        db.save()
        print(f"Fixed {fixed} entr{'y' if fixed == 1 else 'ies'} — database saved.")


# ------------------------------------------------------------------
# enrich
# ------------------------------------------------------------------

def cmd_enrich(args):
    from lib.github_api import load_token, prompt_for_token
    from lib.enrich_db import enrich, find_missing_parents
    from lib.fork_database import ForkDatabase

    if args.dry_run:
        db = ForkDatabase(args.db)
        missing = find_missing_parents(db)
        print(f"Missing parent repos: {len(missing)}")
        if missing:
            print("\nSample (first 20):")
            for fn in missing[:20]:
                print(f"  {fn}")
            if len(missing) > 20:
                print(f"  ... and {len(missing) - 20} more")
        return

    token = args.token or load_token()
    if not token and sys.stdin.isatty():
        token = prompt_for_token()
    if not token:
        print("Warning: No GitHub token. Rate limit is 60 req/hour.")

    db, missing_count, added = enrich(
        db_path=args.db,
        token=token,
        limit=args.limit,
        delay=args.delay,
    )

    stats = db.get_stats()
    print(f"\nDatabase now: {stats['total_repos']:,} repos, {stats['total_forks']:,} forks")
    if missing_count > added + (args.limit or 0):
        remaining = missing_count - (args.limit or missing_count)
        print(f"Still missing: ~{remaining} parents — re-run to continue")


# ------------------------------------------------------------------
# index
# ------------------------------------------------------------------

def cmd_index(args):
    from lib.build_index import build
    sys.exit(build(args.db, args.out, rebuild=args.rebuild))


# ------------------------------------------------------------------
# CLI wiring
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog='db.py',
        description='Fork database operations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 db.py export --csv forks.csv
  python3 db.py export --json forks.json --simple simple.json

  python3 db.py merge github_links_results.json
  python3 db.py merge results1.json results2.json

  python3 db.py enrich                       # fetch all missing parent repos
  python3 db.py enrich --dry-run             # preview what would be fetched
  python3 db.py enrich --limit 500           # fetch up to 500 missing parents

  python3 db.py query --stats
  python3 db.py query --owner celestiaorg
  python3 db.py query --parent 01node/awesome-celestia
  python3 db.py query --top 20

  python3 db.py validate --sample 200
  python3 db.py validate --sample 500 --fix
  python3 db.py validate --owner celestiaorg --fix

  python3 db.py index
  python3 db.py index --rebuild
        """,
    )
    parser.add_argument('--db', default='fork-db/',
                        help='Database directory (default: fork-db/)')

    sub = parser.add_subparsers(dest='command', metavar='COMMAND')
    sub.required = True

    # export
    p_export = sub.add_parser(
        'export',
        help='Export fork relationships to CSV or JSON for external analysis',
        description=(
            'Export fork-db/ relationship data to flat files.\n'
            'No GitHub token or API calls needed — reads only from fork-db/.\n\n'
            'CSV/JSON fields: fork, fork_url, parent, parent_url, source, source_url,\n'
            '                 fork_stars, parent_stars'
        ),
    )
    p_export.add_argument('--csv', metavar='FILE',
                          help='Export full edge list as CSV')
    p_export.add_argument('--json', metavar='FILE',
                          help='Export full edge list as JSON')
    p_export.add_argument('--simple', metavar='FILE',
                          help='Export minimal [{url, parent_url}, ...] JSON')
    p_export.add_argument('--index', metavar='FILE',
                          help='Export flat {full_name: enriched_entry} index JSON for external consumers (includes fork_count and fork_depth)')

    # merge
    p_merge = sub.add_parser(
        'merge',
        help='Merge result JSON file(s) into fork-db/',
        description=(
            'Merge one or more find_forks.py result files into the master database.\n'
            'Existing entries are only replaced if the incoming data is newer\n'
            '(compared by last_checked timestamp).'
        ),
    )
    p_merge.add_argument('sources', nargs='+', metavar='FILE',
                         help='Result JSON file(s) produced by find_forks.py')

    # query
    p_query = sub.add_parser(
        'query',
        help='Query fork relationships and owner repos',
        description='Read and display data from fork-db/. No API calls made.',
    )
    p_query.add_argument('--owner', metavar='USER',
                         help='All repos crawled for a GitHub user/org')
    p_query.add_argument('--info', metavar='REPO',
                         help='Full details for a repo (owner/repo)')
    p_query.add_argument('--parent', metavar='FORK',
                         help='Find the parent of a fork (owner/repo)')
    p_query.add_argument('--search', metavar='NAME',
                         help='Search repos by name')
    p_query.add_argument('--top', type=int, metavar='N',
                         help='Top N most-forked repos')
    p_query.add_argument('--stats', action='store_true',
                         help='Database statistics')
    p_query.add_argument('--random', action='store_true',
                         help='Random repo with its known forks')

    # validate
    p_val = sub.add_parser(
        'validate',
        help='Spot-check stored data against live GitHub API',
        description='Re-fetch a sample of repos and compare against stored data.',
    )
    scope = p_val.add_mutually_exclusive_group(required=True)
    scope.add_argument('--sample', type=int, metavar='N',
                       help='Check N randomly selected repos')
    scope.add_argument('--full', action='store_true',
                       help='Check every repo in the database (slow)')
    scope.add_argument('--owner', metavar='USER',
                       help="Check all repos for one owner")
    p_val.add_argument('--fix', action='store_true',
                       help='Update the database with fresh data for any issues found')
    p_val.add_argument('-t', '--token',
                       help='GitHub API token (overrides GITHUB_TOKEN / .env)')
    p_val.add_argument('--delay', type=float, default=1.5,
                       help='Seconds between API calls (default: 1.5)')

    # enrich
    p_enrich = sub.add_parser(
        'enrich',
        help='Fetch parent repos that are referenced but not yet in the database',
        description=(
            'Scans fork-db/ for parent references that have no entry of their own,\n'
            'then fetches those repos from the GitHub API and writes them directly\n'
            'into fork-db/. Closes the graph gap for analytics.'
        ),
    )
    p_enrich.add_argument('--dry-run', action='store_true',
                          help='Show missing parents without fetching anything')
    p_enrich.add_argument('--limit', type=int, metavar='N',
                          help='Max parents to fetch in this run (re-run to continue)')
    p_enrich.add_argument('-t', '--token',
                          help='GitHub API token (overrides GITHUB_TOKEN / .env)')
    p_enrich.add_argument('--delay', type=float, default=1.5,
                          help='Seconds between API calls (default: 1.5)')

    # index
    p_idx = sub.add_parser(
        'index',
        help='Build or rebuild the SQLite query index',
        description=(
            'Generate fork-db.sqlite from the JSON source files.\n'
            'The index is not committed — regenerate it any time.'
        ),
    )
    p_idx.add_argument('--out', default='fork-db.sqlite',
                       help='Output SQLite file (default: fork-db.sqlite)')
    p_idx.add_argument('--rebuild', action='store_true',
                       help='Delete the existing index and recreate it')

    args = parser.parse_args()

    dispatch = {
        'export':   cmd_export,
        'merge':    cmd_merge,
        'enrich':   cmd_enrich,
        'query':    cmd_query,
        'validate': cmd_validate,
        'index':    cmd_index,
    }
    dispatch[args.command](args)


if __name__ == '__main__':
    main()
