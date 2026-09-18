"""Job scraper sources: Greenhouse, Lever, RemoteOK, Arbeitnow + fixtures.

All fetchers return a normalized job shape:
    {
        "external_id": "greenhouse:12345",
        "source": "greenhouse",
        "title": str,
        "company": str,
        "url": str,
        "location": str | None,
        "description": str,      # plain text, HTML stripped
    }

Every source has an `_http_get_json` helper that raises on HTTP errors so the
caller can fall back to fixtures (PRD rule: fixtures fallback).
"""
import html
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

USER_AGENT = "CareerAgent/1.0 (contact: career-graph-agent)"

NEWLINE_TAGS = re.compile(r"<(br|/p|/li|/h[1-6]|/div|/tr)/?>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")

SOURCE_NAMES = ["greenhouse", "lever", "remoteok", "arbeitnow", "fixture"]


def os_getenv_required(var: str, source: str) -> str:
    val = os.getenv(var)
    if not val:
        raise RuntimeError(f"Source '{source}' needs env var {var} to be set")
    return val


def _http_get_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _strip_html(text: Optional[str]) -> str:
    """Strip HTML tags and collapse whitespace. Returns plain text."""
    if not text:
        return ""
    text = NEWLINE_TAGS.sub("\n", text)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = WHITESPACE_RE.sub(" ", text)
    text = BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _norm(base_id, source, title, company, url, description, location=None) -> Dict:
    return {
        "external_id": f"{source}:{base_id}",
        "source": source,
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "url": (url or "").strip(),
        "location": (location or None),
        "description": _strip_html(description),
    }


# ---------------- Greenhouse ----------------

def fetch_greenhouse(board_token: str, limit: int = 25) -> List[Dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    data = _http_get_json(url)
    jobs = []
    for j in data.get("jobs", [])[:limit]:
        jobs.append(
            _norm(
                j.get("id"),
                "greenhouse",
                j.get("title"),
                j.get("company_name") or board_token,
                j.get("absolute_url"),
                j.get("content", ""),
                (j.get("location") or {}).get("name"),
            )
        )
    return jobs


# ---------------- Lever ----------------

def fetch_lever(company: str, limit: int = 25) -> List[Dict]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    data = _http_get_json(url)
    jobs = []
    for j in (data if isinstance(data, list) else [])[:limit]:
        cat_note = (j.get("categories") or {}).get("location")
        jobs.append(
            _norm(
                j.get("id"),
                "lever",
                j.get("text"),
                j.get("company") or company,
                j.get("hostedUrl") or j.get("applyUrl"),
                j.get("descriptionPlain") or j.get("description", ""),
                cat_note,
            )
        )
    return jobs


# ---------------- RemoteOK ----------------

def fetch_remoteok(limit: int = 25) -> List[Dict]:
    # RemoteOK returns entries whose first row is a legend dict without a
    # "position" field; filter those out.
    data = _http_get_json("https://remoteok.com/api")
    rows = [j for j in (data or []) if isinstance(j, dict) and j.get("position")]
    jobs = []
    for j in rows[:limit]:
        jobs.append(
            _norm(
                j.get("id"),
                "remoteok",
                j.get("position"),
                j.get("company"),
                j.get("url"),
                j.get("description", ""),
                j.get("location"),
            )
        )
    return jobs


# ---------------- Arbeitnow ----------------

def fetch_arbeitnow(limit: int = 25) -> List[Dict]:
    data = _http_get_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for j in (data.get("data") or [])[:limit]:
        slug = j.get("slug")
        url = f"https://www.arbeitnow.com/jobs/{slug}" if slug else j.get("url")
        jobs.append(
            _norm(
                j.get("id") or slug,
                "arbeitnow",
                j.get("title"),
                j.get("company_name") or j.get("company"),
                url,
                j.get("description", ""),
                j.get("location"),
            )
        )
    return jobs


# ---------------- Local fixture fallback ----------------

def fetch_fixtures(path: Optional[str] = None, limit: int = 25) -> List[Dict]:
    """Load fixtures/jobs.json as normalized jobs.

    The fixture shape is `{jobs: [{id, title, company, url, requirements}]}`;
    requirements are kept as-is and consumed directly by JobProcessor.
    """
    if path is None:
        path = str(Path(__file__).resolve().parent.parent.parent / "fixtures" / "jobs.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    jobs = []
    for j in data.get("jobs", [])[:limit]:
        jobs.append(
            {
                "external_id": f"fixture:{j.get('id', j.get('url'))}",
                "source": "fixture",
                "title": j.get("title"),
                "company": j.get("company"),
                "url": j.get("url"),
                "location": j.get("location"),
                "description": j.get("description", ""),
                "requirements": j.get("requirements", []),
            }
        )
    return jobs


# ---------------- Dispatch ----------------

def fetch_source(source: str, limit: int = 25, **kwargs) -> List[Dict]:
    if source == "greenhouse":
        token = kwargs.get("board_token") or os_getenv_required("GREENHOUSE_BOARD_TOKEN", source)
        return fetch_greenhouse(token, limit)
    if source == "lever":
        company = kwargs.get("company") or os_getenv_required("LEVER_COMPANY", source)
        return fetch_lever(company, limit)
    if source == "remoteok":
        return fetch_remoteok(limit)
    if source == "arbeitnow":
        return fetch_arbeitnow(limit)
    if source == "fixture":
        return fetch_fixtures(kwargs.get("fixtures_path"), limit)
    raise ValueError(f"Unknown source: {source}")


def fetch_all(limit_per_source: int = 10, sources: Optional[List[str]] = None, **kwargs) -> List[Dict]:
    """Fetch from multiple sources with per-source caps.

    Sources already configured via env (GREENHOUSE_BOARD_TOKEN, LEVER_COMPANY).
    A failed source falls back to empty list (never crash the whole batch).
    """
    if not sources:
        sources = ["greenhouse", "lever", "remoteok", "arbeitnow"]
    seen, jobs = set(), []
    for src in sources:
        try:
            fetched = fetch_source(src, limit_per_source, **kwargs)
        except Exception as e:
            fetched = []
            print(f"[scraper] source '{src}' failed ({type(e).__name__}: {e}); skipping")
        for j in fetched:
            if j.get("external_id") in seen:
                continue
            seen.add(j.get("external_id"))
            jobs.append(j)
    return jobs