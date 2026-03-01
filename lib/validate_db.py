"""
Validation logic for spot-checking the fork database against live GitHub API data.
Used by db.py validate.
"""

from typing import Dict, List

from .fork_database import ForkDatabase, _utcnow
from .github_api import GitHubAPIClient


ISSUES = ('deleted', 'fork_changed', 'parent_changed', 'source_changed', 'ok')


def check_repo(client: GitHubAPIClient, stored: Dict) -> Dict:
    """
    Re-fetch one repo and compare against what we have stored.
    Returns a result dict: { full_name, status, changes, live_data }
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
