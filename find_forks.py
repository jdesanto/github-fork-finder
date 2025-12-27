#!/usr/bin/env python3
"""
Find GitHub forks and build a collaborative database.

This version is designed to be:
- Additive: Only queries repos not already in database
- Efficient: Checks database before making API calls
- Collaborative: Database file can be merged from multiple contributors
"""

import re
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
import urllib.error

from fork_database import ForkDatabase


class GitHubAPIClient:
    def __init__(self, token: Optional[str] = None, delay: float = 0.5):
        self.token = token
        self.delay = delay
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        self.api_calls_made = 0

    def get_repo_info(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository information from GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}"

        # Check rate limit
        if self.rate_limit_remaining is not None and self.rate_limit_remaining < 10:
            if self.rate_limit_reset:
                wait_time = self.rate_limit_reset - time.time() + 5
                if wait_time > 0:
                    print(f"Rate limit low. Waiting {int(wait_time)} seconds...")
                    time.sleep(wait_time)

        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.token:
            headers['Authorization'] = f'token {self.token}'

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req) as response:
                # Update rate limit info
                self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
                self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))

                data = json.loads(response.read().decode())
                self.api_calls_made += 1

                # Delay for next request
                time.sleep(self.delay)

                return data

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            elif e.code == 403:
                reset_time = int(e.headers.get('X-RateLimit-Reset', 0))
                wait_time = reset_time - time.time() + 5
                if wait_time > 0:
                    print(f"Rate limit exceeded. Waiting {int(wait_time)} seconds...")
                    time.sleep(wait_time)
                    return self.get_repo_info(owner, repo)
            else:
                print(f"Error fetching {owner}/{repo}: {e}")
                return None
        except Exception as e:
            print(f"Unexpected error fetching {owner}/{repo}: {e}")
            return None


def parse_github_urls(file_path: str) -> List[str]:
    """
    Parse GitHub URLs and extract owner/repo.
    Returns list of full_name strings (owner/repo).
    """
    url_pattern = re.compile(r'https://github\.com/([^/]+)/([^/\s]+)')
    repos = set()

    print(f"Parsing {file_path}...")
    with open(file_path, 'r') as f:
        for line in f:
            match = url_pattern.search(line)
            if match:
                owner, repo = match.groups()
                # Clean up repo name
                repo = repo.rstrip('/')
                if repo.endswith('.git'):
                    repo = repo[:-4]
                repos.add(f"{owner}/{repo}")

    return sorted(list(repos))


def main():
    parser = argparse.ArgumentParser(
        description='Build a collaborative database of GitHub forks'
    )
    parser.add_argument(
        'input_file',
        help='File containing GitHub URLs (one per line)'
    )
    parser.add_argument(
        '--db',
        default='fork_database.json',
        help='Database file (default: fork_database.json)'
    )
    parser.add_argument(
        '-t', '--token',
        help='GitHub API token (for higher rate limits)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between API requests in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--export',
        help='Export fork relationships to JSON file'
    )
    parser.add_argument(
        '--export-csv',
        help='Export fork relationships to CSV file'
    )

    args = parser.parse_args()

    # Load database
    print(f"Loading database: {args.db}")
    db = ForkDatabase(args.db)

    # Parse input file
    all_repos = parse_github_urls(args.input_file)
    print(f"Found {len(all_repos)} unique repositories in input file")

    # Check which repos are already in database
    missing_repos = db.get_missing_repos(all_repos)
    already_in_db = len(all_repos) - len(missing_repos)

    print(f"Already in database: {already_in_db}")
    print(f"Need to fetch: {len(missing_repos)}")

    if not missing_repos:
        print("\nAll repositories already in database!")
    else:
        # Fetch missing repos
        print(f"\nFetching {len(missing_repos)} repositories from GitHub API...")

        client = GitHubAPIClient(token=args.token, delay=args.delay)

        for i, full_name in enumerate(missing_repos, 1):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(missing_repos)} ({client.api_calls_made} API calls made)")

            owner, repo = full_name.split('/')
            repo_data = client.get_repo_info(owner, repo)

            if repo_data:
                db.add_repo(full_name, repo_data)
            else:
                # Add a placeholder for not found repos
                db.add_repo(full_name, {
                    'full_name': full_name,
                    'name': repo,
                    'owner': {'login': owner},
                    'fork': False,
                    'html_url': f'https://github.com/{full_name}',
                    'stargazers_count': 0,
                    'forks_count': 0,
                    'created_at': None,
                    'updated_at': None
                })

        print(f"\nCompleted! Made {client.api_calls_made} API calls")

    # Save database
    print("\nSaving database...")
    db.save()

    # Print statistics
    stats = db.get_stats()
    print("\n=== Database Statistics ===")
    print(f"Total repositories: {stats['total_repos']}")
    print(f"Forks: {stats['total_forks']}")
    print(f"Original repos: {stats['original_repos']}")
    print(f"Repositories with forks: {stats['total_parents']}")

    if stats['top_forked']:
        print("\nTop 10 most forked repositories:")
        for repo, count in stats['top_forked']:
            print(f"  {repo}: {count} forks")

    # Export if requested
    if args.export or args.export_csv:
        relationships = db.export_fork_relationships()

        if args.export:
            with open(args.export, 'w') as f:
                json.dump(relationships, f, indent=2)
            print(f"\nExported {len(relationships)} fork relationships to {args.export}")

        if args.export_csv:
            import csv
            with open(args.export_csv, 'w', newline='') as f:
                if relationships:
                    writer = csv.DictWriter(f, fieldnames=relationships[0].keys())
                    writer.writeheader()
                    writer.writerows(relationships)
            print(f"Exported {len(relationships)} fork relationships to CSV: {args.export_csv}")


if __name__ == '__main__':
    main()
