# GitHub Fork Finder

Collaborative database for tracking GitHub repository forks and their relationships.

## 🎯 Overview

This toolkit helps you:

- 🔍 **Find forks** from a list of GitHub repository URLs
- 💾 **Build a database** that grows over time (no duplicate API calls)
- 🤝 **Collaborate** by merging databases from multiple contributors
- ⚡ **Query instantly** to find parents, forks, and relationships
- 📊 **Export** fork relationships to JSON/CSV for analysis

## 🔧 Setup

### Get a GitHub Token (Recommended)

A GitHub token significantly increases your API rate limit from **60 requests/hour** to **5,000 requests/hour**.

**Steps to create a token:**

1. Go to GitHub Settings → [Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Give it a descriptive name (e.g., "Fork Finder")
4. **No special permissions needed** - you can leave all checkboxes unchecked (public data access only)
5. Click **"Generate token"** at the bottom
6. Copy the token (starts with `ghp_...`) - you won't see it again!

**Using your token:**

```bash
# Option 1: Pass as command-line argument
python3 find_forks.py your_links.txt -t ghp_your_token_here

# Option 2: Set as environment variable (recommended)
export GITHUB_TOKEN=ghp_your_token_here
python3 find_forks.py your_links.txt -t $GITHUB_TOKEN
```

**Note:** The token only needs read access to public repositories. Never share your token or commit it to git.

## 🚀 Quick Start

### 1. Find Forks and Build Database

```bash
# Basic usage - outputs to <input>_results.json
python3 find_forks.py your_links.txt -t $GITHUB_TOKEN

# Uses fork-db/ as cache to avoid re-fetching repos
# Output saved to: your_links_results.json

# Specify custom output file
python3 find_forks.py your_links.txt -o my_results.json -t $GITHUB_TOKEN

# Merge results into master database (separate step)
python3 merge_db.py fork-db/ your_links_results.json
```

### 2. Query Fork Relationships

```bash
# Find the parent of any fork
python3 query_db.py --parent owner/fork-repo

# Show complete repository info
python3 query_db.py --info owner/repo

# Search for repositories by name
python3 query_db.py --search awesome-celestia

# List most forked repositories
python3 query_db.py --top 20

# Show database statistics
python3 query_db.py --stats

# Show a random repo with its forks
python3 query_db.py --random
```

### 3. Merge Results into Master Database

```bash
# Merge your results into the master database
python3 merge_db.py fork-db/ your_results.json

# Merge multiple contributor results
python3 merge_db.py fork-db/ contributor1.json contributor2.json

# Or create a new merged database
python3 merge_db.py -o new_master.db db1.json db2.json db3.json
```

## 💾 Storage Formats

The database supports two storage formats, each optimized for different use cases:

### Single-File Format (`.json`)

**Best for:**
- 👤 Individual contributors
- 📤 Easy sharing (single file to transfer)
- 🚀 Simple workflows
- 📊 Output from find_forks.py runs

```bash
# Default output is JSON format
python3 find_forks.py your_links.txt -o my_results.json
```

**Structure:** One JSON file containing all repositories.

**Default use**: This is the default output format when running `find_forks.py`. Each run produces a standalone JSON file that can be easily shared or merged into the master database.

### Directory Format (`.db`)

**Best for:**
- 🏢 Master database (default: `fork-db/`)
- 🔀 Git-friendly collaboration (granular diffs)
- ⚡ Large-scale databases (10,000+ repos, **even millions!**)
- 🗂️ Organized by repository name with **fork families**
- 📊 Clear visualization of fork relationships

```bash
# Master database uses directory format by default
python3 merge_db.py fork-db/ your_results.json
```

**Structure:** Directory tree organized by repository name:
```
fork-db/
├── aw/
│   └── awesome-celestia.json    # All "awesome-celestia" repos organized by fork families
├── co/
│   └── contracts.json           # All "contracts" repos (1,248 repos organized into families)
├── te/
│   └── test.json                # All "test" repos organized by fork families
└── _metadata.json               # Global metadata
```

**Fork families:** Each file organizes repos by their fork relationships:
- **Fork families**: Groups each original repo with its forks
- **Orphaned forks**: Forks whose parent isn't in the database
- **Clear structure**: Easy to see "10 forks of company/test" vs "90 unrelated test repos"

Even with 100+ repos sharing the same name, the structure makes relationships crystal clear.

### Format Comparison

| Feature | Single-File (`.json`) | Directory (`.db`) |
|---------|----------------------|-------------------|
| **File count** | 1 file | 1000s of small files |
| **Load speed** | Fast for small DBs | Fast for large DBs |
| **Save speed** | Writes entire DB | Only writes changed repos |
| **Git diffs** | Large, monolithic | Small, targeted |
| **Sharing** | Copy one file | Zip or git clone |
| **Collaboration** | Merge conflicts possible | Minimal conflicts |
| **Best for** | <10K repos, simple workflows | 10K+ repos, team collaboration |

### Recommended Workflow

**For individual runs**: Use JSON format (default)
```bash
python3 find_forks.py your_links.txt -t $GITHUB_TOKEN
# Output: your_links_results.json
```

**For master database**: Use directory format (fork-db/)
```bash
# Merge JSON results into master database
python3 merge_db.py fork-db/ your_links_results.json
```

**Why this pattern?**
- JSON output is easy to share, email, or attach to PRs
- Master database uses directory format for better git diffs and scalability
- Clean separation: fetching creates JSON, merging updates master
- Cache lookup happens automatically (uses master DB if it exists)

### Format Compatibility

Both formats are fully compatible. You can merge databases regardless of format:

```bash
# All these work seamlessly
python3 merge_db.py fork-db/ contrib1.json contrib2.json
python3 merge_db.py fork-db/ contrib.json
python3 merge_db.py -o merged.db db1.json db2.db db3.json
```

## 📋 Input Format

Create a text file with GitHub URLs (one per line):

```
https://github.com/owner/repo
https://github.com/owner/repo/tree/branch
https://github.com/owner/repo.git
```

The tool automatically extracts `owner/repo` from any GitHub URL format.

**Sample file included:** `sample_links.txt` contains 1,000 sample URLs for testing.

## 🔧 Command Reference

### find_forks.py

Fetch GitHub fork data and output to JSON.

```bash
python3 find_forks.py <input_file> [options]

Options:
  -o, --output FILE  Output JSON file (default: <input_file>_results.json)
  --cache FILE       Master database to use as cache (default: fork-db/)
  -t, --token TOKEN  GitHub API token (recommended for higher rate limits)
  --delay SECONDS    Delay between API calls (default: 0.5)
  --export FILE      Export fork relationships to JSON
  --export-csv FILE  Export fork relationships to CSV
```

**Key behavior:**

- ✅ Uses master database as read-only cache (if it exists)
- ✅ Only fetches repos not already in cache (saves API calls)
- ✅ Outputs results to JSON file (does NOT modify master DB)
- ✅ Shows merge command at end for updating master database

**Rate Limits:**
- Without token: 60 requests/hour
- With token: 5,000 requests/hour
- **Recommendation:** Always use `-t $GITHUB_TOKEN` for any meaningful work

### query_db.py

Query the database to find relationships. Works with both formats.

```bash
python3 query_db.py [options]

Options:
  --db FILE          Database file or directory (default: fork-db/)
                     Supports both .json files and .db directories
  --info REPO        Show detailed info (owner/repo)
  --parent FORK      Find parent of fork (owner/repo)
  --search NAME      Search repos by name
  --top N            List top N most forked repos
  --stats            Show database statistics
  --random           Show a random repo with its forks
```

### merge_db.py

Merge multiple databases together. Handles mixed formats seamlessly.

```bash
python3 merge_db.py <databases...> [options]

Options:
  -o, --output FILE  Output file or directory (default: update first database)

Examples:
  # Merge JSON files into directory database
  python3 merge_db.py main.db contrib1.json contrib2.json

  # Merge everything into new JSON file
  python3 merge_db.py -o merged.json db1.db db2.json db3.db
```

## 💡 Key Features

### 1. Additive & Efficient

The master database acts as a cache - repos are never re-fetched:

```bash
# First run: 100 new repos = 100 API calls
python3 find_forks.py batch1.txt
python3 merge_db.py fork-db/ batch1_results.json

# Second run: 50 new, 50 existing = 50 API calls (50% saved!)
python3 find_forks.py batch2.txt
python3 merge_db.py fork-db/ batch2_results.json

# Third run: all existing = 0 API calls (100% saved!)
python3 find_forks.py all_repos.txt
# Output: All 100 repositories found in cache!
```

### 2. Find Parents Instantly

```bash
$ python3 query_db.py --parent 01node/awesome-celestia

🔱 Fork: 01node/awesome-celestia
⬆️  Parent: celestiaorg/awesome-celestia
   URL: https://github.com/celestiaorg/awesome-celestia
   Stars: ⭐ 45
```

### 3. Collaborative Workflow

**Workflow:** Each contributor runs `find_forks.py` to create a JSON file, then maintainer merges all contributions:

```bash
# Contributors create individual JSON files
python3 find_forks.py alice_repos.txt -o alice_contribution.json -t $ALICE_TOKEN
python3 find_forks.py bob_repos.txt -o bob_contribution.json -t $BOB_TOKEN

# Maintainer merges into master database
python3 merge_db.py fork-db/ alice_contribution.json bob_contribution.json

# Result: JSON contributions automatically integrated into directory structure
```

**Why this pattern?**
- Contributors send a single JSON file (easy to email, attach to PR, or transfer)
- Master database uses directory format for better git diffs and scalability
- Cache prevents duplicate work: if Alice already fetched a repo, Bob gets it from cache
- Merge operation is format-agnostic and handles the conversion automatically

### 4. Export for Analysis

```bash
# Export fork relationships to JSON
python3 find_forks.py links.txt --export relationships.json

# Export to CSV for Excel/spreadsheet analysis
python3 find_forks.py links.txt --export-csv relationships.csv
```

## 📊 Example Queries

### Show Repository Details

```bash
$ python3 query_db.py --info celestiaorg/awesome-celestia

============================================================
📦 celestiaorg/awesome-celestia
============================================================
URL: https://github.com/celestiaorg/awesome-celestia
Owner: celestiaorg
Stars: ⭐ 45
Language: N/A
Description: An Awesome List of Celestia Resources

⭐ This is an ORIGINAL repository

🌳 Forks of this repository (4):
   └─ 01node/awesome-celestia (⭐ 0)
   └─ ChainSafe/awesome-celestia (⭐ 0)
   └─ Sensei-Node/awesome-celestia (⭐ 0)
   └─ decentrio/awesome-celestia (⭐ 0)
```

### Search by Name

```bash
$ python3 query_db.py --search celestia

🔍 Found 5 repositories matching 'celestia':

  🔱 01node/awesome-celestia (⭐ 0)
  🔱 ChainSafe/awesome-celestia (⭐ 0)
  ⭐ celestiaorg/awesome-celestia (⭐ 45)
  🔱 Sensei-Node/awesome-celestia (⭐ 0)
  🔱 decentrio/awesome-celestia (⭐ 0)
```

## 🗄️ Database Formats

### Single-File Format

A single JSON file with sorted keys for clean git diffs:

```json
{
  "updated_at": "2025-12-28T10:30:00Z",
  "total_repos": 1000,
  "total_forks": 450,
  "repos": {
    "owner/repo": {
      "full_name": "owner/repo",
      "is_fork": true,
      "parent": "original-owner/repo",
      "source": "original-owner/repo",
      "stars": 42,
      "created_at": "2024-01-01T00:00:00Z",
      "last_checked": "2025-12-28T10:30:00Z"
    }
  }
}
```

### Directory Format

A directory structure with repos grouped by name and organized into fork families:

**Global metadata** (`_metadata.json`):
```json
{
  "updated_at": "2025-12-28T10:30:00Z",
  "total_repos": 5000,
  "total_forks": 2300,
  "total_files": 4200,
  "unique_repo_names": 4200
}
```

**Individual repo files** (e.g., `aw/awesome-celestia.json`):
```json
{
  "repo_name": "awesome-celestia",
  "last_updated": "2025-12-28T10:30:00Z",
  "total_repos": 5,

  "fork_families": [
    {
      "root": {
        "full_name": "celestiaorg/awesome-celestia",
        "is_fork": false,
        "stars": 45,
        "forks_count": 3,
        ...
      },
      "forks": [
        {
          "full_name": "01node/awesome-celestia",
          "is_fork": true,
          "parent": "celestiaorg/awesome-celestia",
          "stars": 0,
          ...
        },
        {
          "full_name": "ChainSafe/awesome-celestia",
          "parent": "celestiaorg/awesome-celestia",
          ...
        }
      ]
    },
    {
      "root": {
        "full_name": "unrelated-user/awesome-celestia",
        "is_fork": false,
        "stars": 2,
        ...
      },
      "forks": []
    }
  ],

  "orphaned_forks": [
    {
      "full_name": "random/awesome-celestia",
      "is_fork": true,
      "parent": "deleted-user/awesome-celestia",
      ...
    }
  ]
}
```

**Benefits of directory format with fork families:**
- Each file contains repos with the same name, organized by fork relationships
- Easy to see which repos are related (fork families) vs independent
- Handles millions of repos: even if there are 1,000 "test" repos, they're clearly organized
- Git diffs show exactly which repos changed
- Only modified files are rewritten on save
- Subdirectories keep filesystem organized (first 2 letters of repo name)

## 🔑 GitHub API Token

Get higher rate limits (5000/hour vs 60/hour):

1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scope: `public_repo`
4. Use: `python3 find_forks.py links.txt -t YOUR_TOKEN`

## 📈 Performance

- **Without token**: ~60 API calls/hour
- **With token**: ~5000 API calls/hour
- **Caching**: Database prevents duplicate API calls
- **Automatic rate limiting**: Pauses when limit reached

## 🎓 Common Workflows

### Build Over Time

```bash
# Week 1
python3 find_forks.py batch1.txt -t $GITHUB_TOKEN
python3 merge_db.py fork-db/ batch1_results.json

# Week 2 - only fetches new repos!
python3 find_forks.py batch2.txt -t $GITHUB_TOKEN
python3 merge_db.py fork-db/ batch2_results.json

# Query anytime
python3 query_db.py --stats
```

### Team Collaboration

Contributors create JSON files, maintainer merges into master database:

```bash
# Contributors work independently (JSON output by default)
python3 find_forks.py my_repos.txt -t $TOKEN
# Output: my_repos_results.json

# Maintainer merges all contributions into master database
python3 merge_db.py fork-db/ contrib1_results.json contrib2_results.json

# Commit merged database (only changed files in directory format)
git add fork-db/
git commit -m "Merge contributions from contributors"
```

**Benefits:**
- Contributors send single JSON file (easy to share)
- Master database uses directory format (better git diffs)
- Each contributor benefits from cache (no duplicate API calls)
- Maintainer just runs one merge command

## 🐍 Programmatic Access

```python
from fork_database import ForkDatabase

# Works with both formats - automatically detected
db = ForkDatabase('results.json')  # Single-file format
# OR
db = ForkDatabase('fork-db/')    # Directory format

# Query operations (same for both formats)
parent = db.get_parent('owner/fork')
forks = db.get_forks('owner/original')
chain = db.get_fork_chain('owner/nested-fork')
stats = db.get_stats()

# Check current format
print(f"Directory format: {db.is_directory_format}")  # True or False

# Merge databases
db.merge_from_file('contribution.json')
db.save()
```

## 💾 Files

- `find_forks.py` - Build/update database from GitHub URLs
- `query_db.py` - Query relationships
- `merge_db.py` - Merge databases
- `fork_database.py` - Core database class
- `fork_candidates.json` - Pre-analyzed candidates (8,042 repos)
- `sample_links.txt` - 1,000 sample URLs for testing

## 🤝 Contributing

### For Contributors

1. Run find_forks.py to create a JSON file:
   ```bash
   python3 find_forks.py your_repos.txt -t $TOKEN
   # Output: your_repos_results.json
   ```

2. Submit your contribution:
   - Attach `your_repos_results.json` to a GitHub issue/PR
   - Or email the file to the maintainer
   - Or commit it to a contributions folder

### For Maintainers

1. Merge contributions into master database:
   ```bash
   python3 merge_db.py fork-db/ contribution1.json contribution2.json
   ```

2. Commit the merged database:
   ```bash
   git add fork-db/
   git commit -m "Merge contributions"
   ```

**Workflow benefits:**
- **Contributors:** Simple workflow, automatic JSON output
- **Master database:** Directory format for better git diffs and scalability
- **Cache:** Contributors benefit from master DB cache (no duplicate API calls)

## 📝 License

MIT License - See [LICENSE](LICENSE)
