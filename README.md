# GitHub Fork Finder

A toolkit for tracking GitHub repository fork relationships and building a collaborative, human-editable database of who forked what.

## Overview

- **Find forks** from a list of GitHub repository URLs
- **Build a database** that grows incrementally — no duplicate API calls
- **Query instantly** — find parents, forks, fork chains, and all repos by a user
- **Export** fork relationships to JSON/CSV for use in other tools

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
python3 db.py index
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

## Workflow

### Step 1 — Fetch

`find_forks.py` reads a file of GitHub URLs, checks which repos are already cached in `fork-db/`, and fetches the rest from the GitHub API. Results are written to an intermediate JSON file.

```bash
python3 find_forks.py github_links.txt --limit 20000
# Output: github_links_results.json
```

The `--limit` flag caps new API fetches per run. Already-cached repos are always included and never re-fetched, so re-running always picks up where it left off.

### Step 2 — Merge

Once fetching completes, merge the result file into the master database:

```bash
python3 db.py merge github_links_results.json
```

Merge is additive and timestamp-aware: existing entries are only replaced if the incoming data is newer (`last_checked` comparison). The result file can then be discarded — it is already excluded by `.gitignore`.

### Repeat as needed

For large input files, run in chunks across multiple sessions:

```bash
# Session 1
python3 find_forks.py github_links.txt --limit 20000
python3 db.py merge github_links_results.json

# Session 2 — already-cached repos are skipped automatically
python3 find_forks.py github_links.txt --limit 20000
python3 db.py merge github_links_results.json
```

Checkpoint saves happen every 500 repos, so progress is never lost if a run is interrupted mid-way.

### Commit

```bash
git add fork-db/
git commit -m "Add batch from github_links.txt"
```

## Command Reference

### `find_forks.py` — fetch from GitHub API

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

### `db.py` — database operations

#### merge

Merge one or more result files into `fork-db/`.

```bash
python3 db.py merge github_links_results.json
python3 db.py merge results1.json results2.json
python3 db.py merge --db /other/fork-db/ results.json
```

#### query

Read and display data from `fork-db/`. No API calls made.

```bash
# All repos for a specific user (reads one JSON file — no index needed)
python3 db.py query --owner celestiaorg

# Find the parent of a fork
python3 db.py query --parent 01node/awesome-celestia

# Show full info about a repo
python3 db.py query --info celestiaorg/awesome-celestia

# Search repos by name
python3 db.py query --search scaffold-eth

# Top 20 most-forked repos
python3 db.py query --top 20

# Database statistics
python3 db.py query --stats

# Random repo with its known forks
python3 db.py query --random
```

#### validate

Spot-check stored data against live GitHub API responses.

```bash
# Check 200 random repos
python3 db.py validate --sample 200

# Check and fix any stale entries
python3 db.py validate --sample 500 --fix

# Check a specific owner
python3 db.py validate --owner celestiaorg --fix

# Check everything (slow)
python3 db.py validate --full
```

Reports repos checked, % still valid, deleted count, and any field-level changes (fork status, parent, stars). Run with `--fix` to write fresh data back to `fork-db/`.

#### index

Build or rebuild the SQLite query index.

```bash
python3 db.py index             # fork-db/ → fork-db.sqlite
python3 db.py index --rebuild   # drop and recreate
python3 db.py index --out custom.sqlite
```

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

Includes fork URL, parent URL, source URL, and star counts.

## Programmatic Access

```python
from fork_database import ForkDatabase

db = ForkDatabase('fork-db/')

# Provenance — all repos for an owner (reads one JSON file)
repos = db.get_owner_repos('celestiaorg')

# Fork relationships
parent = db.get_parent('01node/awesome-celestia')
forks  = db.get_forks('celestiaorg/awesome-celestia')
chain  = db.get_fork_chain('01node/awesome-celestia')

# Search and stats
results = db.search_by_name('scaffold-eth')
stats   = db.get_stats()

# Build the SQLite index
db.build_sqlite_index('fork-db.sqlite')

# Save changes
db.save()
```

## Files

### Entry points

| File | Purpose |
|---|---|
| `find_forks.py` | Fetch repos from GitHub, write intermediate results JSON |
| `db.py` | Unified CLI: `merge`, `query`, `validate`, `index` |

### Library (`lib/`)

| File | Purpose |
|---|---|
| `lib/fork_database.py` | Core database class |
| `lib/github_api.py` | GitHub API client, token loading, rate-limit handling |
| `lib/query_db.py` | Query functions used by `db.py query` |
| `lib/validate_db.py` | Validation logic used by `db.py validate` |
| `lib/build_index.py` | SQLite index builder used by `db.py index` |
| `lib/merge_db.py` | Merge logic used by `db.py merge` |
| `lib/migrate_db.py` | One-time tool: convert old repo-layout to owner-layout |

### Data & config

| File | Purpose |
|---|---|
| `fork-db/` | Owner-organized JSON database (committed) |
| `fork-db.sqlite` | SQLite query index (not committed, regenerated) |
| `github_links.txt` | Input URLs to process (not committed) |
| `.env` | GitHub token storage (not committed) |

## License

MIT — see [LICENSE](LICENSE)
