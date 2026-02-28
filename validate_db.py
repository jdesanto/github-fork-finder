#!/usr/bin/env python3
"""
Spot-check the fork database against live GitHub API data.

Re-fetches a random sample of repos and compares stored data against the
live API response. Reports correctness statistics and optionally fixes
any discrepancies by updating the JSON source files.

Usage:
  python3 validate_db.py --sample 200           # check 200 random repos
  python3 validate_db.py --sample 500 --fix     # check and fix stale entries
  python3 validate_db.py --full                 # check all repos (slow)
  python3 validate_db.py --owner celestiaorg    # check one owner's repos
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
import urllib.error
from datetime import datetime, timezone

from fork_database import ForkDatabase, _utcnow
from find_forks import load_token, prompt_for_token, GitHubAPIClient


# ------------------------------------------------------------------
# Comparison logic
# ------------------------------------------------------------------

ISSUES = ('deleted', 'fork_changed', 'parent_changed', 'source_changed', 'ok')


def check_repo(client: GitHubAPIClient, stored: Dict) -> Dict:
    """
    Re-fetch one repo and compare against what we have stored.
    Returns a result dict:
      { full_name, status, changes: [...], live_data }
    """
    full_name = stored['full_name']
    owner, repo = full_name.split('/', 1)
    live = client.get_repo_info(owner, repo)

    if live is None:
        return {'full_name': full_name, 'status': 'deleted', 'changes': [], 'live_data': None}

    changes = []
    live_is_fork = live.get('fork', False)
    stored_is_fork = bool(stored.get('is_fork'))

    if stored_is_fork != live_is_fork:
        changes.append(f"is_fork: {stored_is_fork} → {live_is_fork}")

    if live_is_fork:
        live_parent = (live.get('parent') or {}).get('full_name')
        if stored.get('parent') != live_parent:
            changes.append(f"parent: {stored.get('parent')!r} → {live_parent!r}")

        live_source = (live.get('source') or {}).get('full_name')
        if stored.get('source') != live_source:
            changes.append(f"source: {stored.get('source')!r} → {live_source!r}")

    live_stars = live.get('stargazers_count', 0)
    if stored.get('stars', 0) != live_stars:
        changes.append(f"stars: {stored.get('stars')} → {live_stars}")

    status = 'changed' if changes else 'ok'
    return {'full_name': full_name, 'status': status, 'changes': changes, 'live_data': live}


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------

def print_report(results: Dict[str, List], checked: int):
    ok = results['ok']
    changed = results['changed']
    deleted = results['deleted']
    total_issues = len(changed) + len(deleted)

    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Repos checked:        {checked:,}")
    print(f"  Still valid:        {len(ok):,}  ({100*len(ok)/checked:.1f}%)")
    print(f"  Changed:            {len(changed):,}  ({100*len(changed)/checked:.1f}%)")
    print(f"  Deleted / missing:  {len(deleted):,}  ({100*len(deleted)/checked:.1f}%)")

    if changed:
        print(f"\nChanged repos ({min(10, len(changed))} shown):")
        for r in changed[:10]:
            print(f"  {r['full_name']}")
            for c in r['changes']:
                print(f"    {c}")

    if deleted:
        print(f"\nDeleted repos ({min(10, len(deleted))} shown):")
        for r in deleted[:10]:
            print(f"  {r['full_name']}")

    if total_issues == 0:
        print("\nAll checked repos look correct!")
    else:
        print(f"\n{total_issues} issue(s) found.")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Spot-check the fork database against live GitHub API data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 validate_db.py --sample 200
  python3 validate_db.py --sample 500 --fix
  python3 validate_db.py --full
  python3 validate_db.py --owner celestiaorg --fix
        """,
    )
    parser.add_argument('--db', default='fork-db/',
                        help='Database directory (default: fork-db/)')
    parser.add_argument('--sample', type=int, metavar='N',
                        help='Check N randomly selected repos')
    parser.add_argument('--full', action='store_true',
                        help='Check every repo in the database (slow)')
    parser.add_argument('--owner', metavar='USER',
                        help='Check only repos belonging to this owner')
    parser.add_argument('--fix', action='store_true',
                        help='Update the database with fresh data for any issues found')
    parser.add_argument('-t', '--token',
                        help='GitHub API token (overrides GITHUB_TOKEN / .env)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Seconds between API requests (default: 0.5)')

    args = parser.parse_args()

    if not args.sample and not args.full and not args.owner:
        parser.error("Specify --sample N, --full, or --owner USER")

    # Resolve token
    token = args.token or load_token()
    if not token and sys.stdin.isatty():
        token = prompt_for_token()
    if not token:
        print("Warning: No GitHub token. Rate limit is 60 req/hour.")

    # Load database
    print(f"Loading database: {args.db}")
    db = ForkDatabase(args.db)
    total_db = len(db.repos)
    print(f"Loaded {total_db:,} repos")

    if total_db == 0:
        print("Database is empty.")
        return

    # Build the sample to check
    if args.owner:
        candidates = [fn for fn in db.repos if fn.split('/')[0].lower() == args.owner.lower()]
        if not candidates:
            print(f"No repos found for owner '{args.owner}'")
            return
        sample = candidates
        print(f"Checking {len(sample)} repos for owner '{args.owner}'...")
    elif args.full:
        sample = list(db.repos.keys())
        print(f"Checking all {len(sample):,} repos...")
    else:
        n = min(args.sample, total_db)
        sample = random.sample(list(db.repos.keys()), n)
        print(f"Checking {n:,} random repos from {total_db:,} total...")

    client = GitHubAPIClient(token=token, delay=args.delay)
    results: Dict[str, List] = {'ok': [], 'changed': [], 'deleted': []}

    for i, full_name in enumerate(sample, 1):
        if i % 50 == 0 or i == len(sample):
            pct = 100 * i / len(sample)
            print(f"  {i}/{len(sample)} ({pct:.0f}%) — "
                  f"{client.api_calls_made} API calls")

        stored = db.get_repo(full_name)
        result = check_repo(client, stored)
        bucket = result['status'] if result['status'] in ('deleted', 'ok') else 'changed'
        results[bucket].append(result)

        if result['status'] != 'ok':
            icon = '🗑' if result['status'] == 'deleted' else '⚠'
            print(f"  {icon} {full_name}: {result['status']}")
            for change in result['changes']:
                print(f"      {change}")

    print_report(results, len(sample))
    print(f"API calls made: {client.api_calls_made:,}")

    total_issues = len(results['changed']) + len(results['deleted'])

    if total_issues > 0 and not args.fix:
        print(f"\nRun with --fix to update {total_issues} stale entr{'y' if total_issues == 1 else 'ies'}.")
        return

    if args.fix and total_issues > 0:
        print(f"\nFixing {total_issues} entr{'y' if total_issues == 1 else 'ies'}...")
        fixed = 0

        for result in results['changed']:
            if result['live_data']:
                db.add_repo(result['full_name'], result['live_data'])
                fixed += 1

        for result in results['deleted']:
            # Keep the record but annotate it so it's not re-fetched repeatedly
            stored = db.get_repo(result['full_name'])
            if stored:
                stored['last_checked'] = _utcnow()
                stored['deleted'] = True
                db.add_repo_entry(stored)
                fixed += 1

        db.save()
        print(f"Fixed {fixed} entr{'y' if fixed == 1 else 'ies'} — database saved.")


if __name__ == '__main__':
    main()
