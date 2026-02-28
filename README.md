# GitHub Fork Finder

A toolkit for tracking GitHub repository fork relationships and building a collaborative, human-editable database of who forked what.

## Overview

- **Find forks** from a list of GitHub repository URLs
- **Build a database** that grows incrementally — no duplicate API calls
- **Query instantly** — find parents, forks, fork chains, and all repos by a user
- **Export** fork relationships to JSON/CSV for use in other tools
- **Collaborate** by merging result files from multiple contributors

## Storage Design

### Primary store: `fork-db/` (committed to git)

One JSON file per GitHub owner/org. Finding all repos for a user is a single file open.

```
fork-db/
  _metadata.json
  ce/
    celestiaorg.json      ← every repo crawled for "celestiaorg"
  01/
    01node.json
  sc/
    scaffold-eth.json
  ...
```

Each owner file has a slim schema focused on fork relationships:

```json
{
  "owner": "celestiaorg",
  "updated_at": "2025-12-30T09:17Z",
  "repos": [
    {
      "full_name": "celestiaorg/celestia-node",
      "is_fork": false,
      "parent": null,
      "source": null,
      "stars": 1234,
      "language": "Go",
      "last_checked": "2025-12-30T09:17Z"
    },
    {
      "full_name": "celestiaorg/cosmos-sdk",
      "is_fork": true,
      "parent": "cosmos/cosmos-sdk",
      "source": "cosmos/cosmos-sdk",
      "stars": 12,
      "language": "Go",
      "last_checked": "2025-12-30T09:17Z"
    }
  ]
}
```

Files are human-readable, directly editable, and produce clean git diffs (a change to one owner's repos only touches their file).

### Query index: `fork-db.sqlite` (not committed)

A SQLite file built from the JSON source. Used for cross-owner queries (`--top`, `--search`, `--stats`). Regenerate any time:

```bash
python3 build_index.py
```

The JSON files are always the source of truth. The SQLite file is a derived artifact.

## Setup

### GitHub Token

A token raises the API rate limit from **60 req/hour** to **5,000 req/hour**. No scopes are needed for public repo data.

1. Go to **github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Generate a new token, leave all scopes unchecked
3. Copy the token (starts with `ghp_`)

The token is read automatically from (in priority order):

1. `-t TOKEN` command-line flag
2. `GITHUB_TOKEN` environment variable
3. A `.env` file in the project directory (`GITHUB_TOKEN=ghp_...`)
4. Interactive prompt on first run — offers to save to `.env`

```bash
# Or just run and let it prompt you:
python3 find_forks.py github_links.txt
```

## Quick Start

### Fetch repos and update database

```bash
# Fetch up to 20,000 new repos (default limit), using fork-db/ as cache
python3 find_forks.py github_links.txt

# Smaller chunks for testing
python3 find_forks.py github_links.txt --limit 1000

# Merge results into the master database
python3 merge_db.py fork-db/ github_links_results.json

# Rebuild the query index
python3 build_index.py --rebuild
```

### Query the database

```bash
# All repos for a specific user (reads one JSON file — no index needed)
python3 query_db.py --owner celestiaorg

# Find the parent of a fork
python3 query_db.py --parent 01node/awesome-celestia

# Show full info about a repo
python3 query_db.py --info celestiaorg/awesome-celestia

# Search repos by name
python3 query_db.py --search scaffold-eth

# Top 20 most-forked repos
python3 query_db.py --top 20

# Database statistics
python3 query_db.py --stats

# Random repo with its forks
python3 query_db.py --random
```

### Spot-check data quality

```bash
# Check 200 random repos against live GitHub data
python3 validate_db.py --sample 200

# Check and fix any stale entries
python3 validate_db.py --sample 500 --fix

# Check a specific owner
python3 validate_db.py --owner celestiaorg --fix
```

## Processing Large Input Files

`github_links.txt` can contain hundreds of thousands of URLs. Use `--limit` to process in chunks. The cache means re-running always picks up where it left off:

```bash
# Day 1: process first 20k uncached repos (~4 hours with a token)
python3 find_forks.py github_links.txt --limit 20000
python3 merge_db.py fork-db/ github_links_results.json

# Day 2: automatically skips the 20k already cached
python3 find_forks.py github_links.txt --limit 20000
python3 merge_db.py fork-db/ github_links_results.json

# Repeat until all URLs are covered
```

Checkpoint saves happen every 500 repos so progress is never lost if the run is interrupted.

## Command Reference

### `find_forks.py`

Fetch repo data from GitHub and write results to a JSON file.

```
python3 find_forks.py <input_file> [options]

Arguments:
  input_file              File of GitHub URLs, one per line

Options:
  -o, --output FILE       Output JSON file (default: <input>_results.json)
  --cache DIR             Master database to use as cache (default: fork-db/)
  --limit N               Max new API fetches per run (default: 20000)
  -t, --token TOKEN       GitHub API token
  --delay SECONDS         Seconds between API calls (default: 0.5)
  --export FILE           Export fork relationships to JSON
  --export-csv FILE       Export fork relationships to CSV
  --export-simple FILE    Export simple {url, parent_url} format to JSON
```

### `query_db.py`

```
python3 query_db.py [options]

Options:
  --db DIR           Database directory (default: fork-db/)
  --owner USER       List all repos crawled for a GitHub user/org
  --info REPO        Show detailed info (owner/repo)
  --parent FORK      Find the parent of a fork (owner/repo)
  --search NAME      Search repos by name
  --top N            Top N most forked repos
  --stats            Database statistics
  --random           Random repo with its forks
```

### `merge_db.py`

Merge one or more result files into the master database.

```
python3 merge_db.py fork-db/ results.json
python3 merge_db.py fork-db/ results1.json results2.json
python3 merge_db.py -o merged/ db1/ contrib.json
```

Accepts any mix of owner-organized directories, old `fork_families` directories, and single-file JSON. Merges only use newer data (compares `last_checked` timestamps).

### `build_index.py`

Build or rebuild the SQLite query index from the JSON files.

```
python3 build_index.py                        # fork-db/ → fork-db.sqlite
python3 build_index.py --db fork-db/ --out custom.sqlite
python3 build_index.py --rebuild              # drop and recreate
```

### `migrate_db.py`

Convert an old `fork_families`-format database to the new owner-organized format.

```
python3 migrate_db.py old-fork-db/ new-fork-db/ --verify
```

### `validate_db.py`

Spot-check stored data against live GitHub API responses.

```
python3 validate_db.py --sample 200          # check 200 random repos
python3 validate_db.py --sample 500 --fix    # check and fix stale entries
python3 validate_db.py --full                # check everything (slow)
python3 validate_db.py --owner celestiaorg   # check one owner
```

Reports: repos checked, % still valid, deleted count, fork-status changes, parent changes.

## Export Formats

### Simple (recommended for external tools)

```bash
python3 find_forks.py links.txt --export-simple forks.json
```

```json
[
  { "url": "https://github.com/torvalds/linux",  "parent_url": null },
  { "url": "https://github.com/user/linux",       "parent_url": "https://github.com/torvalds/linux" }
]
```

### Full relationship export

```bash
python3 find_forks.py links.txt --export relationships.json
python3 find_forks.py links.txt --export-csv relationships.csv
```

Includes fork URL, parent URL, source URL, star counts.

## Programmatic Access

```python
from fork_database import ForkDatabase

db = ForkDatabase('fork-db/')

# Provenance — all repos for an owner (reads one JSON file)
repos = db.get_owner_repos('celestiaorg')

# Fork relationships
parent     = db.get_parent('01node/awesome-celestia')
forks      = db.get_forks('celestiaorg/awesome-celestia')
chain      = db.get_fork_chain('01node/awesome-celestia')

# Search and stats
results    = db.search_by_name('scaffold-eth')
stats      = db.get_stats()

# Build the SQLite index
db.build_sqlite_index('fork-db.sqlite')

# Save changes
db.save()
```

## Files

| File | Purpose |
|---|---|
| `find_forks.py` | Fetch repos from GitHub, write results JSON |
| `merge_db.py` | Merge result files into master database |
| `query_db.py` | Query fork relationships and provenance |
| `build_index.py` | Build SQLite query index from JSON files |
| `migrate_db.py` | Convert old format database to new owner layout |
| `validate_db.py` | Spot-check database against live GitHub data |
| `fork_database.py` | Core database class |
| `fork-db/` | Owner-organized JSON database (committed) |
| `fork-db.sqlite` | SQLite query index (not committed, regenerated) |
| `github_links.txt` | Input URLs to process (not committed) |
| `.env` | GitHub token storage (not committed) |

## Contributing

```bash
# 1. Fetch repos and create a result file
python3 find_forks.py your_repos.txt
# Output: your_repos_results.json

# 2. Submit the result file as a PR or attachment
```

Maintainers merge contributions with:

```bash
python3 merge_db.py fork-db/ contribution.json
python3 build_index.py --rebuild
git add fork-db/
git commit -m "Merge contributions"
```

## License

MIT — see [LICENSE](LICENSE)
