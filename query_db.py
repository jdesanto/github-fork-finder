#!/usr/bin/env python3
"""
Query the fork database to find parents, forks, and relationships.
"""

import argparse
import random
import sys
from fork_database import ForkDatabase


def print_repo_info(db: ForkDatabase, full_name: str):
    """Print detailed information about a repository."""
    repo = db.get_repo(full_name)

    if not repo:
        print(f"❌ Repository '{full_name}' not found in database")
        return

    print(f"\n{'='*60}")
    print(f"📦 {repo['full_name']}")
    print(f"{'='*60}")
    print(f"URL: {repo['html_url']}")
    print(f"Owner: {repo['owner']}")
    print(f"Stars: ⭐ {repo['stars']}")
    print(f"Language: {repo['language'] or 'N/A'}")
    print(f"Description: {repo['description'] or 'No description'}")
    print(f"Created: {repo['created_at'] or 'Unknown'}")
    print(f"Updated: {repo['updated_at'] or 'Unknown'}")

    if repo['is_fork']:
        print(f"\n🔱 This is a FORK")
        if repo['parent']:
            print(f"   Parent: {repo['parent']}")
        if repo['source'] and repo['source'] != repo['parent']:
            print(f"   Source: {repo['source']} (original)")

        # Show fork chain
        chain = db.get_fork_chain(full_name)
        if len(chain) > 1:
            print(f"\n📊 Fork Chain ({len(chain)} levels):")
            for i, ancestor in enumerate(chain):
                indent = "   " * i
                if i == 0:
                    print(f"{indent}└─ {ancestor} (you are here)")
                elif i == len(chain) - 1:
                    print(f"{indent}└─ {ancestor} (original)")
                else:
                    print(f"{indent}└─ {ancestor}")
    else:
        print(f"\n⭐ This is an ORIGINAL repository")

    # Show forks of this repo
    forks = db.get_forks(full_name)
    if forks:
        print(f"\n🌳 Forks of this repository ({len(forks)}):")
        for fork in sorted(forks)[:20]:  # Show first 20
            fork_data = db.get_repo(fork)
            stars = fork_data['stars'] if fork_data else 0
            print(f"   └─ {fork} (⭐ {stars})")
        if len(forks) > 20:
            print(f"   ... and {len(forks) - 20} more")

    print()


def search_repos(db: ForkDatabase, name: str):
    """Search for repositories by name."""
    results = db.search_by_name(name)

    if not results:
        print(f"❌ No repositories found matching '{name}'")
        return

    print(f"\n🔍 Found {len(results)} repositories matching '{name}':\n")
    for full_name in sorted(results)[:50]:  # Show first 50
        repo = db.get_repo(full_name)
        status = "🔱" if repo['is_fork'] else "⭐"
        stars = repo['stars']
        print(f"  {status} {full_name} (⭐ {stars})")

    if len(results) > 50:
        print(f"\n  ... and {len(results) - 50} more results")


def find_parent(db: ForkDatabase, fork_name: str):
    """Find the parent of a fork."""
    parent = db.get_parent(fork_name)

    if not parent:
        repo = db.get_repo(fork_name)
        if not repo:
            print(f"❌ Repository '{fork_name}' not found in database")
        elif not repo['is_fork']:
            print(f"ℹ️  '{fork_name}' is not a fork (it's an original repository)")
        else:
            print(f"⚠️  '{fork_name}' is marked as a fork but parent is unknown")
        return

    print(f"\n🔱 Fork: {fork_name}")
    print(f"⬆️  Parent: {parent}")

    # Show parent info
    parent_data = db.get_repo(parent)
    if parent_data:
        print(f"   URL: {parent_data['html_url']}")
        print(f"   Stars: ⭐ {parent_data['stars']}")


def list_top_forked(db: ForkDatabase, limit: int = 20):
    """List the most forked repositories."""
    stats = db.get_stats()

    print(f"\n🏆 Top {limit} Most Forked Repositories:\n")
    for i, (repo, count) in enumerate(stats['top_forked'][:limit], 1):
        repo_data = db.get_repo(repo)
        stars = repo_data['stars'] if repo_data else 0
        print(f"{i:2d}. {repo}")
        print(f"    └─ {count} forks | ⭐ {stars} stars")


def show_stats(db: ForkDatabase):
    """Show database statistics."""
    stats = db.get_stats()

    print(f"\n{'='*60}")
    print(f"📊 DATABASE STATISTICS")
    print(f"{'='*60}")
    print(f"Total repositories:     {stats['total_repos']:,}")
    print(f"  ⭐ Original repos:     {stats['original_repos']:,}")
    print(f"  🔱 Forks:              {stats['total_forks']:,}")
    print(f"Repos with forks:       {stats['total_parents']:,}")
    print()


def show_random_fork_example(db: ForkDatabase):
    """Show a random repository that has forks."""
    # Get all repos that have forks (either in DB or reported by GitHub)
    repos_with_forks_in_db = []
    repos_with_fork_count = []

    for full_name, repo in db.repos.items():
        if not repo['is_fork']:  # Only original repos
            forks = db.get_forks(full_name)
            if forks:
                repos_with_forks_in_db.append((full_name, forks))
            elif repo.get('forks_count', 0) > 0:
                repos_with_fork_count.append(full_name)

    # Prefer repos where we have the actual forks in the database
    if repos_with_forks_in_db:
        parent_name, forks = random.choice(repos_with_forks_in_db)
        parent = db.get_repo(parent_name)

        print(f"\n{'='*60}")
        print(f"🎲 RANDOM FORK EXAMPLE")
        print(f"{'='*60}")
        print(f"\n⭐ Original: {parent_name}")
        print(f"   URL: {parent['html_url']}")
        print(f"   Stars: ⭐ {parent['stars']}")
        if parent['description']:
            desc = parent['description'][:80] + '...' if len(parent['description']) > 80 else parent['description']
            print(f"   Description: {desc}")

        print(f"\n🌳 Forks ({len(forks)}):")
        # Show up to 10 forks, sorted by stars
        fork_data = [(fork, db.get_repo(fork)['stars']) for fork in forks if db.get_repo(fork)]
        fork_data.sort(key=lambda x: x[1], reverse=True)

        for fork_name, stars in fork_data[:10]:
            print(f"   └─ {fork_name} (⭐ {stars})")

        if len(forks) > 10:
            print(f"   ... and {len(forks) - 10} more forks")
        print()

    elif repos_with_fork_count:
        # Fall back to showing repos with fork count (but forks not in DB)
        parent_name = random.choice(repos_with_fork_count)
        parent = db.get_repo(parent_name)

        print(f"\n{'='*60}")
        print(f"🎲 RANDOM FORK EXAMPLE")
        print(f"{'='*60}")
        print(f"\n⭐ Original: {parent_name}")
        print(f"   URL: {parent['html_url']}")
        print(f"   Stars: ⭐ {parent['stars']}")
        print(f"   Forks: {parent['forks_count']} (not in database)")
        if parent['description']:
            desc = parent['description'][:80] + '...' if len(parent['description']) > 80 else parent['description']
            print(f"   Description: {desc}")

        print(f"\n💡 Note: The {parent['forks_count']} fork(s) of this repo are not in the database.")
        print(f"   To see fork details, add them to your input list and run find_forks.py")
        print()

    else:
        print("❌ No repositories with forks found in database")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Query the GitHub fork database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show info about a specific repo
  python query_db.py --info celestiaorg/awesome-celestia

  # Find the parent of a fork
  python query_db.py --parent 01node/awesome-celestia

  # Search for repos by name
  python query_db.py --search awesome-celestia

  # List most forked repositories
  python query_db.py --top 20

  # Show database statistics
  python query_db.py --stats

  # Show a random repo with its forks
  python query_db.py --random
        """
    )

    parser.add_argument(
        '--db',
        default='fork-db/',
        help='Database file or directory (default: fork-db/)'
    )

    parser.add_argument(
        '--info',
        metavar='REPO',
        help='Show detailed info about a repository (owner/repo)'
    )

    parser.add_argument(
        '--parent',
        metavar='FORK',
        help='Find the parent of a fork (owner/repo)'
    )

    parser.add_argument(
        '--search',
        metavar='NAME',
        help='Search for repositories by name'
    )

    parser.add_argument(
        '--top',
        type=int,
        metavar='N',
        help='List top N most forked repositories'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )

    parser.add_argument(
        '--random',
        action='store_true',
        help='Show a random repository with its forks'
    )

    args = parser.parse_args()

    # Load database
    db = ForkDatabase(args.db)

    # Execute query
    if args.info:
        print_repo_info(db, args.info)
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
        print("\n💡 Tip: Use --help to see examples")


if __name__ == '__main__':
    main()
