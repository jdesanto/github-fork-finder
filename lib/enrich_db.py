"""
Parent enrichment — fetch all parent repos that are referenced by forks in the
database but not yet present as their own entries.

Closing this gap turns the fork graph from a collection of disconnected
spoke-hub pairs into a properly connected graph suitable for analytics.
"""

from typing import Optional

from .fork_database import ForkDatabase
from .github_api import GitHubAPIClient


def find_missing_parents(db: ForkDatabase) -> list:
    """Return a sorted list of parent full_names not yet in the database."""
    return sorted({
        entry['parent']
        for entry in db.repos.values()
        if entry.get('parent') and entry['parent'] not in db.repos
    })


def enrich(
    db_path: str,
    token: Optional[str],
    limit: Optional[int] = None,
    delay: float = 0.5,
) -> tuple:
    """
    Fetch missing parent repos and write them directly into the database.
    Returns (db, missing_count, added_count).
    """
    db = ForkDatabase(db_path)
    missing = find_missing_parents(db)
    missing_count = len(missing)

    print(f"Found {missing_count} parent repos not yet in database")

    if not missing:
        print("Nothing to enrich.")
        return db, 0, 0

    if limit and len(missing) > limit:
        missing = missing[:limit]
        print(f"Limiting to {limit} (re-run to continue)")

    print(f"Fetching {len(missing)} repos from GitHub API...\n")

    client = GitHubAPIClient(token=token, delay=delay)
    added = 0

    for i, full_name in enumerate(missing, 1):
        if i % 100 == 0 or i == 1:
            pct = 100 * i / len(missing)
            print(f"  {i}/{len(missing)} ({pct:.0f}%) — "
                  f"{client.api_calls_made} API calls — "
                  f"{client.rate_limit_remaining or '?'} rate-limit remaining")

        owner, repo = full_name.split('/', 1)
        repo_data = client.get_repo_info(owner, repo)

        if repo_data:
            db.add_repo(full_name, repo_data)
            added += 1
        else:
            # Repo is 404 / deleted — add a placeholder so we don't retry it
            db.add_repo(full_name, {
                'full_name': full_name,
                'name': repo,
                'owner': {'login': owner},
                'fork': False,
                'stargazers_count': 0,
            })

        if i % 500 == 0:
            db.save()
            print(f"  Checkpoint saved at {i} repos")

    db.save()
    print(f"\nCompleted: {added} parent repos added ({len(missing) - added} were 404/deleted)")
    print(f"API calls made: {client.api_calls_made:,}")

    return db, missing_count, added
