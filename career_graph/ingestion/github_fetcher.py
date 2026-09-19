"""GitHub API fetcher: username -> repo metadata for the ingestion pipeline.

PRD Layer 2 expects a Lambda that calls the GitHub API (repos, languages,
README, commit stats) and feeds the results to extraction. This module does
the same using the public REST API, optionally authenticated via GITHUB_TOKEN
(60 req/hr unauthenticated vs 5000 authenticated).
"""
import base64
import json
import re
import urllib.request
from typing import Any, Dict, List, Optional

USER_AGENT = "CareerAgent/1.0 (career-graph-agent)"


def _headers(token: Optional[str] = None) -> Dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _gh_get(url: str, token: Optional[str] = None, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _commit_count(owner: str, repo: str, token: Optional[str]) -> int:
    """Approximate commit count via the Link header page number trick."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            link = resp.headers.get("Link", "")
        if link:
            m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
            if m:
                return int(m.group(1))
        return 1 if link else 0
    except Exception:
        return 0


def _readme_text(owner: str, repo: str, token: Optional[str]) -> str:
    try:
        data = _gh_get(f"https://api.github.com/repos/{owner}/{repo}/readme", token)
        content = data.get("content") or ""
        enc = data.get("encoding")
        if enc == "base64" or not enc:
            content = base64.b64decode(content).decode("utf-8", errors="replace")
        return content[:6000]
    except Exception:
        return ""


def fetch_github_repos(username: str, token: Optional[str] = None, max_repos: int = 100) -> List[Dict[str, Any]]:
    """Fetch the user's public repos, enriched with languages/README/commits."""
    repos = _gh_get(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated", token)
    if not isinstance(repos, list):
        raise RuntimeError(f"Unexpected GitHub response for '{username}': {repos}")

    results: List[Dict[str, Any]] = []
    for r in repos[:max_repos]:
        name = r.get("name")
        owner = r.get("owner", {}).get("login") or username
        try:
            languages = _gh_get(f"https://api.github.com/repos/{owner}/{name}/languages", token)
        except Exception:
            languages = {}
        primary = max(languages, key=languages.get) if isinstance(languages, dict) and languages else r.get("language")
        results.append(
            {
                "name": name,
                "html_url": r.get("html_url"),
                "description": r.get("description"),
                "language": primary,
                "commits_count": _commit_count(owner, name, token),
                "readme_text": _readme_text(owner, name, token),
            }
        )
    return results