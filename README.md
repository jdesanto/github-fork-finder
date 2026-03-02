# GitHub Fork Finder

A toolkit for building and querying a database of GitHub repository fork relationships. The database tracks which repos are forks of which, enabling analysis of how open-source ecosystems branch and grow.

`fork-db/` is committed to this repository and can be used directly — no GitHub token or API calls needed to query or export the existing data.

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

`parent` is the immediate upstream repo. `source` is the ultimate root of the fork chain. Files are human-readable and produce clean git diffs.

### Query index: `fork-db.sqlite` (not committed)

A SQLite file built from the JSON source for fast cross-owner queries. Regenerate any time:

```bash
python3 db.py index
```

---

## Using the data

No GitHub token required. No dependencies beyond Python 3.8+.

### Clone and query

```bash
git clone https://github.com/jdesanto/github-fork-finder.git
cd github-fork-finder

python3 db.py query --stats
python3 db.py query --owner celestiaorg
python3 db.py query --top 20
python3 db.py query --parent 01node/awesome-celestia
python3 db.py query --search scaffold-eth
```

### Export for analysis

```bash
# Full edge list — fork, parent, source, star counts (CSV or JSON)
python3 db.py export --csv forks.csv
python3 db.py export --json forks.json

# Minimal format: [{url, parent_url}, ...] — good for graph tools
python3 db.py export --simple simple.json

# Flat index — {full_name: enriched_entry} with fork_count and fork_depth
python3 db.py export --index fork-index.json

# Combine formats in one pass
python3 db.py export --csv forks.csv --index fork-index.json
```

> **Note:** `--csv` and `--json` only include fork edges where the parent repo is also present in `fork-db/`. Run `db.py enrich` (see below) to maximize coverage before exporting. `--simple` and `--index` always include all repos.

### Programmatic access

```python
from lib.fork_database import ForkDatabase

db = ForkDatabase('fork-db/')

# Provenance — all repos for an owner (reads one JSON file)
repos = db.get_owner_repos('celestiaorg')

# Fork relationships
parent = db.get_parent('01node/awesome-celestia')
forks  = db.get_forks('celestiaorg/awesome-celestia')
chain  = db.get_fork_chain('01node/awesome-celestia')

# Export to flat structures for pandas / NetworkX
edges  = db.export_fork_relationships()  # list of dicts with fork/parent/source/stars
simple = db.export_simple()              # [{url, parent_url}, ...]
index  = db.export_index()               # {full_name: {…, fork_count, fork_depth}}

# Stats
stats  = db.get_stats()
```

---

## Integration

`fork-db/` stores the raw data. External tools that need a single queryable file can generate a flat index:

```bash
python3 db.py enrich              # pull missing parent repos first (improves graph completeness)
python3 db.py export --index fork-index.json
```

`fork-index.json` maps every `full_name` to its enriched entry:

```json
{
  "celestiaorg/cosmos-sdk": {
    "is_fork": true,
    "parent": "cosmos/cosmos-sdk",
    "source": "cosmos/cosmos-sdk",
    "stars": 12,
    "language": "Go",
    "last_checked": "2025-12-30T09:17Z",
    "fork_count": 3,
    "fork_depth": 1
  },
  ...
}
```

| Field | Meaning |
|---|---|
| `parent` | Immediate upstream repo (`null` for originals) |
| `source` | Root of the fork chain (`null` for originals) |
| `fork_count` | Number of known direct forks of this repo |
| `fork_depth` | Depth in the chain — 0 for originals, 1 for direct forks, 2+ for forks-of-forks |

`fork-index.json` is excluded from git (see `.gitignore`). Regenerate it after each `db.py merge` or `db.py enrich` cycle.

---

## Extending the data

To fetch more repos or refresh existing entries, you need a GitHub API token.

### GitHub token setup

A token raises the rate limit from **60 req/hour** to **5,000 req/hour**. No scopes are needed for public repo data.

1. Go to **github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Generate a new token, leave all scopes unchecked
3. Copy the token (starts with `ghp_`)

The token is read from (in priority order):

1. `-t TOKEN` CLI flag
2. `GITHUB_TOKEN` environment variable
3. `.env` file in the project root (`GITHUB_TOKEN=ghp_...`)
4. Interactive prompt on first run — offers to save to `.env`

### Fetch → Merge workflow

**Step 1 — Fetch**

`find_forks.py` reads a file of GitHub URLs, skips anything already in `fork-db/`, and fetches the rest from the API. Results go to an intermediate JSON file.

```bash
python3 find_forks.py github_links.txt --limit 20000
# Output: github_links_results.json
```

`--limit` caps new API calls per run. Re-running always picks up where it left off.

**Step 2 — Merge**

```bash
python3 db.py merge github_links_results.json
```

Merge is additive and timestamp-aware — existing entries are only replaced if the incoming data is newer. The results file can be discarded after merging (it is already excluded by `.gitignore`).

**Step 3 — Enrich (recommended before exporting)**

Many forks reference parent repos that weren't in the input file. `enrich` fetches those parents directly, which is essential for connected graph analysis.

```bash
python3 db.py enrich --dry-run   # preview what would be fetched
python3 db.py enrich             # fetch all missing parents
python3 db.py enrich --limit 500 # chunked, re-run to continue
```

**Step 4 — Commit**

```bash
git add fork-db/
git commit -m "Add batch from github_links.txt"
```

### Processing large input files

Run in chunks across sessions — the cache means already-fetched repos are never re-fetched:

```bash
# Session 1
python3 find_forks.py github_links.txt --limit 20000
python3 db.py merge github_links_results.json

# Session 2 — skips the 20k already in fork-db/
python3 find_forks.py github_links.txt --limit 20000
python3 db.py merge github_links_results.json
```

Checkpoint saves happen every 500 repos — progress is never lost if a run is interrupted.

---

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
  --delay SECONDS         Seconds between API calls (default: 1.5)
  --export FILE           Export fork relationships to JSON
  --export-csv FILE       Export fork relationships to CSV
  --export-simple FILE    Export simple {url, parent_url} format to JSON
```

### `db.py` — database operations

#### export

Export fork relationships to flat files for analysis. No API calls.

```bash
python3 db.py export --csv forks.csv
python3 db.py export --json forks.json
python3 db.py export --simple simple.json
python3 db.py export --index fork-index.json
```

| Flag | Format | Contents |
|---|---|---|
| `--csv FILE` | CSV | Fork edges (requires parent in db) |
| `--json FILE` | JSON array | Fork edges (requires parent in db) |
| `--simple FILE` | JSON array | `[{url, parent_url}, ...]` for all repos |
| `--index FILE` | JSON object | `{full_name: enriched_entry}` for all repos, includes `fork_count` and `fork_depth` |

CSV/JSON edge fields: `fork`, `fork_url`, `parent`, `parent_url`, `source`, `source_url`, `fork_stars`, `parent_stars`

#### merge

Merge one or more result files into `fork-db/`.

```bash
python3 db.py merge github_links_results.json
python3 db.py merge results1.json results2.json
python3 db.py merge --db /other/fork-db/ results.json
```

#### enrich

Fetch parent repos that are referenced by forks but not yet in the database.

```bash
python3 db.py enrich --dry-run       # preview missing parents
python3 db.py enrich                 # fetch all missing parents
python3 db.py enrich --limit 1000    # chunked, re-run to continue
```

#### query

Read and display data from `fork-db/`. No API calls.

```bash
python3 db.py query --stats
python3 db.py query --owner celestiaorg
python3 db.py query --parent 01node/awesome-celestia
python3 db.py query --info celestiaorg/awesome-celestia
python3 db.py query --search scaffold-eth
python3 db.py query --top 20
python3 db.py query --random
```

#### validate

Spot-check stored data against live GitHub API responses.

```bash
python3 db.py validate --sample 200
python3 db.py validate --sample 500 --fix
python3 db.py validate --owner celestiaorg --fix
python3 db.py validate --full
```

#### index

Build or rebuild the SQLite query index.

```bash
python3 db.py index
python3 db.py index --rebuild
python3 db.py index --out custom.sqlite
```

---

## Files

### Entry points

| File | Purpose |
|---|---|
| `find_forks.py` | Fetch repos from GitHub, write intermediate results JSON |
| `db.py` | Unified CLI: `export`, `merge`, `enrich`, `query`, `validate`, `index` |

### Library (`lib/`)

| File | Purpose |
|---|---|
| `lib/fork_database.py` | Core database class |
| `lib/github_api.py` | GitHub API client, token loading, rate-limit handling |
| `lib/export_db.py` | Export logic used by `db.py export` |
| `lib/query_db.py` | Query functions used by `db.py query` |
| `lib/validate_db.py` | Validation logic used by `db.py validate` |
| `lib/enrich_db.py` | Parent enrichment logic used by `db.py enrich` |
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
