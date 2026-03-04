"""
Export fork relationships from fork-db/ to flat files for external analysis.
Used by db.py export.

Output formats:
  --csv     edge list with fork, parent, source, star counts
  --json    same data as CSV but JSON array
  --simple  minimal [{url, parent_url}, ...] format
"""

import csv
import json
from pathlib import Path

from .fork_database import ForkDatabase


def export(
    db_path: str,
    csv_path: str = None,
    json_path: str = None,
    simple_path: str = None,
    index_path: str = None,
) -> dict:
    """
    Export fork relationships from the database to one or more output files.
    Returns a summary dict with counts.
    """
    db = ForkDatabase(db_path)
    summary = {}

    if csv_path or json_path:
        relationships = db.export_fork_relationships()
        summary['relationships'] = len(relationships)

        if json_path:
            out = Path(json_path)
            out.write_text(
                json.dumps(relationships, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
            print(f"Exported {len(relationships):,} fork relationships → {out}")

        if csv_path:
            out = Path(csv_path)
            with out.open('w', encoding='utf-8', newline='') as f:
                if relationships:
                    writer = csv.DictWriter(f, fieldnames=relationships[0].keys())
                    writer.writeheader()
                    writer.writerows(relationships)
            print(f"Exported {len(relationships):,} fork relationships → {out}")

    if simple_path:
        simple = db.export_simple()
        out = Path(simple_path)
        out.write_text(
            json.dumps(simple, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        summary['simple'] = len(simple)
        print(f"Exported {len(simple):,} repos in simple format → {out}")

    if index_path:
        index = db.export_index()
        out = Path(index_path)
        out.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        summary['index'] = len(index)
        print(f"Exported {len(index):,} repos in index format → {out}")

    return summary
