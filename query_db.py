#!/usr/bin/env python3
"""
Query the fork database to find parents, forks, relationships, and owner repos.
"""

import argparse
import random
import sys
from pathlib import Path
from fork_database import ForkDatabase


def print_repo_info(db: ForkDatabase, full_name: str):
    """Print detailed information about a repository."""
    repo = db.get_repo(full_name)

    if not repo:
        print(f"Repository '{full_name}' not found in database")
        return

    print(f"\n{'='*60}")
    print(f"{repo['full_name']}")
    print(f"{'='*60}")
    print(f"URL:      https://github.com/{repo['full_name']}")
    print(f"Stars:    {repo.get('stars', 0)}")
    print(f"Language: {repo.get('language') or 'N/A'}")
    print(f"Checked:  {repo.get('last_checked') or 'Unknown'}")

    if repo.get('is_fork'):
        print(f"\nThis is a FORK")
        if repo.get('parent'):
            print(f"  Parent: {repo['parent']}")
        if repo.get('source') and repo.get('source') != repo.get('parent'):
            print(f"  Source: {repo['source']} (original)")

        chain = db.get_fork_chain(full_name)
        if len(chain) > 1:
            print(f"\nFork chain ({len(chain)} levels):")
            for i, ancestor in enumerate(chain):
                indent = "   " * i
                suffix = " (you are here)" if i == 0 else (" (original)" if i == len(chain) - 1 else "")
                print(f"{indent}└─ {ancestor}{suffix}")
    else:
        print(f"\nThis is an ORIGINAL repository")

    forks = db.get_forks(full_name)
    if forks:
        print(f"\nKnown forks ({len(forks)}):")
        for fork in sorted(forks)[:20]:
            fork_data = db.get_repo(fork)
            stars = fork_data.get('stars', 0) if fork_data else 0
            print(f"   └─ {fork} ({stars} stars)")
        if len(forks) > 20:
            print(f"   ... and {len(forks) - 20} more")
    print()


def print_owner_repos(db: ForkDatabase, owner: str):
    """Print all repos crawled for a given owner."""
    repos = db.get_owner_repos(owner)

    if not repos:
        print(f"No repos found for owner '{owner}'")
        return

    forks = [r for r in repos if r.get('is_fork')]
    originals = [r for r in repos if not r.get('is_fork')]

    print(f"\n{'='*60}")
    print(f"Owner: {owner}  ({len(repos)} repos)")
    print(f"{'='*60}")

    if originals:
        print(f"\nOriginal repos ({len(originals)}):")
        for r in sorted(originals, key=lambda x: x.get('stars', 0), reverse=True):
            lang = f"  [{r.get('language')}]" if r.get('language') else ""
            print(f"  {r['full_name']}  ({r.get('stars', 0)} stars){lang}")

    if forks:
        print(f"\nForks ({len(forks)}):")
        for r in sorted(forks, key=lambda x: x['full_name']):
            parent = r.get('parent', '?')
            print(f"  {r['full_name']}  ← {parent}")
    print()


def search_repos(db: ForkDatabase, name: str):
    """Search for repositories by name."""
    results = db.search_by_name(name)

    if not results:
        print(f"No repositories found matching '{name}'")
        return

    print(f"\nFound {len(results)} repositories matching '{name}':\n")
    for full_name in sorted(results)[:50]:
        repo = db.get_repo(full_name)
        if not repo:
            continue
        status = "FORK" if repo.get('is_fork') else "orig"
        stars = repo.get('stars', 0)
        print(f"  [{status}] {full_name} ({stars} stars)")

    if len(results) > 50:
        print(f"\n  ... and {len(results) - 50} more results")


def find_parent(db: ForkDatabase, fork_name: str):
    """Find the parent of a fork."""
    parent = db.get_parent(fork_name)

    if not parent:
        repo = db.get_repo(fork_name)
        if not repo:
            print(f"Repository '{fork_name}' not found in database")
        elif not repo.get('is_fork'):
            print(f"'{fork_name}' is not a fork (it's an original repository)")
        else:
            print(f"'{fork_name}' is marked as a fork but its parent is unknown")
        return

    print(f"\nFork:   {fork_name}")
    print(f"Parent: {parent}")

    parent_data = db.get_repo(parent)
    if parent_data:
        print(f"  URL:   https://github.com/{parent}")
        print(f"  Stars: {parent_data.get('stars', 0)}")


def list_top_forked(db: ForkDatabase, limit: int = 20):
    """List the most forked repositories."""
    stats = db.get_stats()
    print(f"\nTop {limit} Most Forked Repositories:\n")
    for i, (repo, count) in enumerate(stats['top_forked'][:limit], 1):
        repo_data = db.get_repo(repo)
        stars = repo_data.get('stars', 0) if repo_data else 0
        print(f"{i:2d}. {repo}")
        print(f"    └─ {count} forks | {stars} stars")


def show_stats(db: ForkDatabase):
    """Show database statistics."""
    stats = db.get_stats()
    print(f"\n{'='*60}")
    print(f"DATABASE STATISTICS")
    print(f"{'='*60}")
    print(f"Total repositories:     {stats['total_repos']:,}")
    print(f"  Original repos:       {stats['original_repos']:,}")
    print(f"  Forks:                {stats['total_forks']:,}")
    print(f"Repos with known forks: {stats['total_parents']:,}")
    print()


def show_random_fork_example(db: ForkDatabase):
    """Show a random repository that has forks in the database."""
    repos_with_forks = [
        (full_name, db.get_forks(full_name))
        for full_name, repo in db.repos.items()
        if not repo.get('is_fork') and db.get_forks(full_name)
    ]

    if not repos_with_forks:
        print("No repositories with known forks found in database")
        return

    parent_name, forks = random.choice(repos_with_forks)
    parent = db.get_repo(parent_name)

    print(f"\n{'='*60}")
    print(f"RANDOM FORK EXAMPLE")
    print(f"{'='*60}")
    print(f"\nOriginal: {parent_name}")
    print(f"  URL:    https://github.com/{parent_name}")
    print(f"  Stars:  {parent.get('stars', 0) if parent else 0}")

    print(f"\nKnown forks ({len(forks)}):")
    fork_data = [
        (fork, db.get_repo(fork))
        for fork in forks
        if db.get_repo(fork)
    ]
    fork_data.sort(key=lambda x: x[1].get('stars', 0), reverse=True)

    for fork_name, fdata in fork_data[:10]:
        print(f"   └─ {fork_name} ({fdata.get('stars', 0)} stars)")

    if len(forks) > 10:
        print(f"   ... and {len(forks) - 10} more")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Query the GitHub fork database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 query_db.py --info celestiaorg/awesome-celestia
  python3 query_db.py --owner celestiaorg
  python3 query_db.py --parent 01node/awesome-celestia
  python3 query_db.py --search awesome-celestia
  python3 query_db.py --top 20
  python3 query_db.py --stats
  python3 query_db.py --random
        """,
    )

    parser.add_argument('--db', default='fork-db/',
                        help='Database directory (default: fork-db/)')
    parser.add_argument('--info', metavar='REPO',
                        help='Show detailed info about a repo (owner/repo)')
    parser.add_argument('--owner', metavar='USER',
                        help='List all repos crawled for a GitHub user/org')
    parser.add_argument('--parent', metavar='FORK',
                        help='Find the parent of a fork (owner/repo)')
    parser.add_argument('--search', metavar='NAME',
                        help='Search for repositories by name')
    parser.add_argument('--top', type=int, metavar='N',
                        help='List top N most forked repositories')
    parser.add_argument('--stats', action='store_true',
                        help='Show database statistics')
    parser.add_argument('--random', action='store_true',
                        help='Show a random repository with its forks')

    args = parser.parse_args()

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
        parser.print_help()
        print("\nTip: use --help to see examples")


if __name__ == '__main__':
    main()
