"""
GitHub API client, token helpers, and timing utilities.
Shared by find_forks.py, enrich_db.py, and validate_db.py.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.error


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string (e.g. '1h23m', '4m22s')."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m{s:02d}s"
    else:
        h, remainder = divmod(seconds, 3600)
        m = remainder // 60
        return f"{h}h{m:02d}m"


def load_token() -> Optional[str]:
    """Return a GitHub token from GITHUB_TOKEN env var or a .env file."""
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        return token.strip()
    env_file = Path('.env')
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('GITHUB_TOKEN=') and not line.startswith('#'):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return None


def prompt_for_token() -> Optional[str]:
    """Interactively ask for a token and offer to save it to .env."""
    print("\nNo GitHub API token found.")
    print("A token gives you 5,000 req/hour vs 60/hour unauthenticated.")
    print("Create one at: https://github.com/settings/tokens (no scopes needed for public repos)")
    try:
        token = input("Enter token (or press Enter to continue without one): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not token:
        return None
    try:
        save = input("Save to .env for future runs? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        save = 'n'
    if save == 'y':
        env_file = Path('.env')
        env_file.write_text(f"GITHUB_TOKEN={token}\n", encoding='utf-8')
        print(f"Token saved to {env_file}")
    return token


class GitHubAPIClient:
    def __init__(self, token: Optional[str] = None, delay: float = 1.5):
        self.token = token
        self.delay = delay
        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_reset: Optional[int] = None
        self.api_calls_made = 0

    def get_repo_info(self, owner: str, repo: str) -> Optional[Dict]:
        """Fetch repository metadata from the GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}"

        # Iterative loop so repeated 403s don't overflow the stack
        for attempt in range(3):
            if self.rate_limit_remaining is not None and self.rate_limit_remaining < 10:
                if self.rate_limit_reset:
                    wait = self.rate_limit_reset - time.time() + 5
                    if wait > 0:
                        print(f"Rate limit low ({self.rate_limit_remaining} left). "
                              f"Waiting {int(wait)}s...")
                        time.sleep(wait)

            headers = {'Accept': 'application/vnd.github.v3+json'}
            if self.token:
                headers['Authorization'] = f'Bearer {self.token}'

            req = urllib.request.Request(url, headers=headers)

            try:
                with urllib.request.urlopen(req) as resp:
                    self.rate_limit_remaining = int(
                        resp.headers.get('X-RateLimit-Remaining', 5000)
                    )
                    self.rate_limit_reset = int(
                        resp.headers.get('X-RateLimit-Reset', 0)
                    )
                    data = json.loads(resp.read().decode())
                    self.api_calls_made += 1
                    time.sleep(self.delay)
                    return data

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                elif e.code == 403:
                    reset_time = int(e.headers.get('X-RateLimit-Reset', 0))
                    wait = reset_time - time.time() + 5
                    if wait > 0 and attempt < 2:
                        print(f"Rate limit exceeded. Waiting {int(wait)}s "
                              f"(attempt {attempt + 1}/3)...")
                        time.sleep(wait)
                        continue
                    print(f"Rate limit: giving up after 3 attempts for {owner}/{repo}")
                    return None
                else:
                    print(f"HTTP {e.code} fetching {owner}/{repo}: {e}")
                    return None
            except Exception as e:
                print(f"Unexpected error fetching {owner}/{repo}: {e}")
                return None

        return None
