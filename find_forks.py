#!/usr/bin/env python3
"""
Find GitHub forks and build a collaborative database.

This script is designed to be:
- Additive:    Only queries repos not already in the cache database
- Idempotent:  Re-running skips anything already cached; picks up where it left off
- Chunked:     --limit caps the number of new API calls per run (default 20,000)
- Efficient:   Checks the cache before every API call
- Collaborative: Output file can be merged into the master database
"""

import csv
import json
import re
import sys
import argparse
from pathlib import Path
from typing import List

from lib.fork_database import ForkDatabase
from lib.github_api import load_token, prompt_for_token, GitHubAPIClient


# ------------------------------------------------------------------
# Input parsing
# ------------------------------------------------------------------

def parse_github_urls(file_path: str) -> List[str]:
    """Parse GitHub repo URLs from a file. Returns sorted list of owner/repo strings."""
    url_pattern = re.compile(r'https://github\.com/([^/\s]+)/([^/\s]+)')
    repos: set = set()

    print(f"Parsing {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = url_pattern.search(line)
            if m:
                owner, repo = m.groups()
                repo = repo.rstrip('/')
                if repo.endswith('.git'):
                    repo = repo[:-4]
                repos.add(f"{owner}/{repo}")

    return sorted(repos)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Fetch GitHub fork data and write results to a JSON file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 find_forks.py github_links.txt
  python3 find_forks.py github_links.txt --limit 20000
  python3 find_forks.py github_links.txt --cache fork-db/ -o results.json
  python3 find_forks.py github_links.txt -t ghp_yourtoken
        """,
    )
    parser.add_argument('input_file', help='File of GitHub URLs (one per line)')
    parser.add_argument('-o', '--output',
                        help='Output JSON file (default: <input>_results.json)')
    parser.add_argument('--cache', default='fork-db/',
                        help='Master database used as a read cache (default: fork-db/)')
    parser.add_argument('-t', '--token',
                        help='GitHub API token (overrides GITHUB_TOKEN env / .env)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Seconds between API requests (default: 0.5)')
    parser.add_argument('--limit', type=int, default=20000, metavar='N',
                        help='Max new API calls per run (default: 20000). '
                             'Already-cached repos are always included regardless of limit.')
    parser.add_argument('--export',
                        help='Also export fork relationships to this JSON file')
    parser.add_argument('--export-csv',
                        help='Also export fork relationships to this CSV file')
    parser.add_argument('--export-simple',
                        help='Also export simple (url + parent_url) format to this JSON file')

    args = parser.parse_args()

    # Resolve token: CLI flag > env/file > interactive prompt
    token = args.token or load_token()
    if not token and sys.stdin.isatty():
        token = prompt_for_token()
    if not token:
        print("Warning: No GitHub token. Rate limit is 60 req/hour.")

    # Output filename
    output_file = args.output or (Path(args.input_file).stem + '_results.json')

    # Load cache database (read-only reference)
    cache_db = None
    if Path(args.cache).exists():
        print(f"Loading cache from: {args.cache}")
        cache_db = ForkDatabase(args.cache)
        print(f"Cache contains {len(cache_db.repos)} repos")
    else:
        print(f"No cache found at {args.cache} — will fetch all repos")

    # Create output database (single-file JSON)
    output_db = ForkDatabase(output_file)

    # Parse input and split into cached / missing
    all_repos = parse_github_urls(args.input_file)
    print(f"Found {len(all_repos)} unique repositories in input")

    cached_repos: List[str] = []
    missing_repos: List[str] = []

    for repo in all_repos:
        if cache_db and cache_db.has_repo(repo):
            output_db.add_repo_entry(cache_db.get_repo(repo))
            cached_repos.append(repo)
        else:
            missing_repos.append(repo)

    print(f"Found in cache: {len(cached_repos)}")
    print(f"Need to fetch:  {len(missing_repos)}")

    # Apply per-run limit
    if args.limit and len(missing_repos) > args.limit:
        print(f"Applying --limit {args.limit}: "
              f"will fetch {args.limit} of {len(missing_repos)} uncached repos")
        missing_repos = missing_repos[:args.limit]

    if missing_repos:
        print(f"\nFetching {len(missing_repos)} repositories from GitHub API...")
        client = GitHubAPIClient(token=token, delay=args.delay)

        for i, full_name in enumerate(missing_repos, 1):
            if i % 100 == 0 or i == 1:
                pct = 100 * i / len(missing_repos)
                print(f"  {i}/{len(missing_repos)} ({pct:.0f}%) — "
                      f"{client.api_calls_made} API calls — "
                      f"{client.rate_limit_remaining or '?'} rate-limit remaining")

            owner, repo = full_name.split('/', 1)
            repo_data = client.get_repo_info(owner, repo)

            if repo_data:
                output_db.add_repo(full_name, repo_data)
            else:
                # Placeholder for repos that returned 404
                output_db.add_repo(full_name, {
                    'full_name': full_name,
                    'name': repo,
                    'owner': {'login': owner},
                    'fork': False,
                    'html_url': f'https://github.com/{full_name}',
                    'stargazers_count': 0,
                    'forks_count': 0,
                    'created_at': None,
                    'updated_at': None,
                })

            # Periodic checkpoint saves (every 500 repos)
            if i % 500 == 0:
                output_db.save()
                print(f"  Checkpoint saved at {i} repos")

        print(f"\nCompleted! Made {client.api_calls_made} API calls")
    else:
        print("\nAll repositories found in cache!")

    # Final save
    print(f"\nSaving results to {output_file}...")
    output_db.save()

    # Statistics
    stats = output_db.get_stats()
    print("\n=== Results ===")
    print(f"Total repositories:       {stats['total_repos']}")
    print(f"Forks:                    {stats['total_forks']}")
    print(f"Original repos:           {stats['original_repos']}")
    print(f"Repos with known forks:   {stats['total_parents']}")

    if stats['top_forked']:
        print("\nTop 10 most forked:")
        for repo, count in stats['top_forked']:
            print(f"  {repo}: {count} forks")

    print(f"\nOutput saved to: {output_file}")
    if missing_repos:
        remaining = len(all_repos) - len(cached_repos) - len(missing_repos)
        if remaining > 0:
            print(f"Still uncached: ~{remaining} repos (re-run to continue)")
        print(f"Merge into master: python3 merge_db.py {args.cache} {output_file}")

    # Optional exports
    if args.export or args.export_csv:
        relationships = output_db.export_fork_relationships()

        if args.export:
            with open(args.export, 'w', encoding='utf-8') as f:
                json.dump(relationships, f, indent=2, ensure_ascii=False)
            print(f"Exported {len(relationships)} fork relationships → {args.export}")

        if args.export_csv:
            with open(args.export_csv, 'w', encoding='utf-8', newline='') as f:
                if relationships:
                    writer = csv.DictWriter(f, fieldnames=relationships[0].keys())
                    writer.writeheader()
                    writer.writerows(relationships)
            print(f"Exported {len(relationships)} fork relationships → {args.export_csv}")

    if args.export_simple:
        simple = output_db.export_simple()
        with open(args.export_simple, 'w', encoding='utf-8') as f:
            json.dump(simple, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(simple)} repos in simple format → {args.export_simple}")


if __name__ == '__main__':
    main()
