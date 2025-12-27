# GitHub Fork Finder

Collaborative database for tracking GitHub repository forks and their relationships.

## 🎯 Overview

This toolkit helps you:

- 🔍 **Find forks** from a list of GitHub repository URLs
- 💾 **Build a database** that grows over time (no duplicate API calls)
- 🤝 **Collaborate** by merging databases from multiple contributors
- ⚡ **Query instantly** to find parents, forks, and relationships
- 📊 **Export** fork relationships to JSON/CSV for analysis

## 🚀 Quick Start

### 1. Find Forks and Build Database

```bash
# Basic usage - builds/updates fork_database.json by default
python3 find_forks.py your_links.txt -t $GITHUB_TOKEN

# Save to a different database file
python3 find_forks.py your_links.txt --db my_database.json -t $GITHUB_TOKEN

# The database automatically appends new results!
# Run again with more links - only new repos are fetched
python3 find_forks.py more_links.txt -t $GITHUB_TOKEN
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
```

### 3. Merge Databases (For Collaboration)

```bash
# Merge contributor databases into main database
python3 merge_db.py fork_database.json contributor1.json contributor2.json

# Or create a new merged database
python3 merge_db.py -o merged.json db1.json db2.json db3.json
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

Build or update the fork database.

```bash
python3 find_forks.py <input_file> [options]

Options:
  --db FILE          Database file (default: fork_database.json)
  -t, --token TOKEN  GitHub API token (recommended for higher rate limits)
  --delay SECONDS    Delay between API calls (default: 0.5)
  --export FILE      Export fork relationships to JSON
  --export-csv FILE  Export fork relationships to CSV
```

**Key behavior:**

- ✅ Automatically checks which repos are already in database
- ✅ Only fetches missing repos (saves API calls)
- ✅ Appends results to existing database by default
- ✅ Creates new database if none exists

### query_db.py

Query the database to find relationships.

```bash
python3 query_db.py [options]

Options:
  --db FILE          Database file (default: fork_database.json)
  --info REPO        Show detailed info (owner/repo)
  --parent FORK      Find parent of fork (owner/repo)
  --search NAME      Search repos by name
  --top N            List top N most forked repos
  --stats            Show database statistics
```

### merge_db.py

Merge multiple databases together.

```bash
python3 merge_db.py <databases...> [options]

Options:
  -o, --output FILE  Output file (default: update first database)
```

## 💡 Key Features

### 1. Additive & Efficient

The database acts like a cache - repos are never re-fetched:

```bash
# First run: 100 new repos = 100 API calls
python3 find_forks.py batch1.txt

# Second run: 50 new, 50 existing = 50 API calls (50% saved!)
python3 find_forks.py batch2.txt

# Third run: all existing = 0 API calls (100% saved!)
python3 find_forks.py all_repos.txt
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

Multiple contributors can build databases separately and merge them:

```bash
# Alice builds her database
python3 find_forks.py alice_repos.txt --db alice.json -t $ALICE_TOKEN

# Bob builds his database
python3 find_forks.py bob_repos.txt --db bob.json -t $BOB_TOKEN

# Maintainer merges both into main database
python3 merge_db.py fork_database.json alice.json bob.json
```

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

## 🗄️ Database Format

The database is stored as JSON with sorted keys for clean git diffs:

```json
{
  "version": "1.0",
  "updated_at": "2025-12-27T10:30:00Z",
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
      "last_checked": "2025-12-27T10:30:00Z"
    }
  }
}
```

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

# Week 2 - only fetches new repos!
python3 find_forks.py batch2.txt -t $GITHUB_TOKEN

# Query anytime
python3 query_db.py --stats
```

### Team Collaboration

```bash
# Contributors work independently
python3 find_forks.py my_repos.txt --db contribution.json -t $TOKEN

# Maintainer merges
python3 merge_db.py fork_database.json contribution1.json contribution2.json

# Commit merged database
git add fork_database.json
git commit -m "Merge contributions"
```

## 🐍 Programmatic Access

```python
from fork_database import ForkDatabase

db = ForkDatabase('fork_database.json')

# Find parent
parent = db.get_parent('owner/fork')

# Get forks
forks = db.get_forks('owner/original')

# Get fork chain
chain = db.get_fork_chain('owner/nested-fork')

# Stats
stats = db.get_stats()
```

## 💾 Files

- `find_forks.py` - Build/update database from GitHub URLs
- `query_db.py` - Query relationships
- `merge_db.py` - Merge databases
- `fork_database.py` - Core database class
- `fork_candidates.json` - Pre-analyzed candidates (8,042 repos)
- `sample_links.txt` - 1,000 sample URLs for testing

## 🤝 Contributing

1. Build your database: `python3 find_forks.py your_repos.txt --db contribution.json -t $TOKEN`
2. Commit and create pull request
3. Maintainer merges with `merge_db.py`

Sorted JSON ensures clean diffs!

## 📝 License

MIT License - See [LICENSE](LICENSE)
