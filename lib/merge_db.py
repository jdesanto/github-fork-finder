"""
Merge logic — used by db.py merge.
"""

from pathlib import Path

from .fork_database import ForkDatabase


def merge(base_path: str, sources: list) -> tuple:
    """
    Merge source files/directories into the base database.
    Returns (initial_count, total_added).
    """
    base_db = ForkDatabase(base_path)
    initial = len(base_db.repos)
    total_added = 0

    for source in sources:
        if not Path(source).exists():
            print(f"  Skipping {source} (not found)")
            continue
        print(f"Merging {source}...")
        added = base_db.merge_from_file(source)
        total_added += added
        print(f"  +{added} repos")

    base_db.save()
    return base_db, initial, total_added
