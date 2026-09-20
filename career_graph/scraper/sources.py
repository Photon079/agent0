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

SOURCE_NAMES = ["greenhouse", "lever", "remoteok", "remotive", "adzuna", "jsearch", "fixture"]

# Tech job keyword filter — only jobs matching these in title/tags are kept
TECH_KEYWORDS = {
    "software", "engineer", "engineering", "developer", "dev", "backend", "frontend",
    "full-stack", "fullstack", "data", "machine learning", "ml", "ai", "python",
    "javascript", "typescript", "react", "node", "java", "golang", "rust", "cloud",
    "devops", "sre", "infrastructure", "platform", "security", "architect",
    "mobile", "ios", "android", "web", "api", "database", "analytics", "scientist",
    "embedded", "firmware", "compiler", "kernel", "systems", "product manager",
    "technical", "tech", "programmer", "coding", "coder", "it ", "qa ", "testing",
    "kubernetes", "docker", "aws", "gcp", "azure", "linux",
}


def _is_tech_job(title: str, tags: list = None) -> bool:
    """Return True if the job title or tags indicate a tech/software role."""
    haystack = (title or "").lower()
    if tags:
        haystack += " " + " ".join(t.lower() for t in tags)
    return any(kw in haystack for kw in TECH_KEYWORDS)


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
    for j in rows:
        title = j.get("position", "")
        tags = j.get("tags") or []
        if not _is_tech_job(title, tags):
            continue
        jobs.append(
            _norm(
                j.get("id"),
                "remoteok",
                title,
                j.get("company"),
                j.get("url"),
                j.get("description", ""),
                j.get("location"),
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


# ---------------- Arbeitnow ----------------

def fetch_arbeitnow(limit: int = 25) -> List[Dict]:
    data = _http_get_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for j in (data.get("data") or []):
        title = j.get("title", "")
        tags = j.get("tags") or []
        if not _is_tech_job(title, tags):
            continue
        # Use the full URL returned by the API directly — building from slug gives 404s
        url = j.get("url")
        jobs.append(
            _norm(
                j.get("id") or j.get("slug"),
                "arbeitnow",
                title,
                j.get("company_name") or j.get("company"),
                url,
                j.get("description", ""),
                j.get("location"),
            )
        )
        if len(jobs) >= limit:
            break
    return jobs


# ---------------- Remotive (replaces Arbeitnow) ----------------

REMOTIVE_CATEGORIES = [
    "software-dev",
    "data",
    "devops-sysadmin",
]

def fetch_remotive(limit: int = 25) -> List[Dict]:
    """Remotive: free public API for remote tech jobs globally. No key needed."""
    jobs = []
    seen_ids: set = set()
    for cat in REMOTIVE_CATEGORIES:
        if len(jobs) >= limit:
            break
        try:
            data = _http_get_json(f"https://remotive.com/api/remote-jobs?category={cat}&limit={limit}")
        except Exception:
            continue
        for j in data.get("jobs", []):
            if len(jobs) >= limit:
                break
            jid = str(j.get("id", ""))
            if jid in seen_ids:
                continue
            seen_ids.add(jid)
            jobs.append(
                _norm(
                    jid,
                    "remotive",
                    j.get("title"),
                    j.get("company_name"),
                    j.get("url"),
                    j.get("description", ""),
                    j.get("candidate_required_location") or "Remote",
                )
            )
    return jobs


# ---------------- JSearch via OpenWebNinja — aggregates LinkedIn + Indeed + Glassdoor ----------------

def fetch_jsearch(api_key: str, query: str = "software engineer India", limit: int = 25) -> List[Dict]:
    """JSearch via OpenWebNinja: aggregates LinkedIn, Indeed, Google Jobs.
    Requires JSEARCH_API_KEY (X-API-Key header).
    API: https://api.openwebninja.com/jsearch/search-v2
    """
    import requests as _requests
    resp = _requests.get(
        "https://api.openwebninja.com/jsearch/search-v2",
        params={"query": query},
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for j in (data.get("data", {}).get("jobs") or [])[:limit]:
        title = j.get("job_title", "")
        if not _is_tech_job(title):
            continue
        location = (
            ", ".join(filter(None, [j.get("job_city"), j.get("job_state"), j.get("job_country")]))
            or None
        )
        jobs.append(
            _norm(
                j.get("job_id"),
                "jsearch",
                title,
                j.get("employer_name"),
                j.get("job_apply_link") or j.get("job_google_link"),
                j.get("job_description", ""),
                location,
            )
        )
    return jobs



def fetch_adzuna(app_id: str, app_key: str, limit: int = 25, country: str = "in") -> List[Dict]:
    """Adzuna job search. Defaults to India (country='in'). Set ADZUNA_COUNTRY env to override."""
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        f"?app_id={app_id}&app_key={app_key}&results_per_page={limit}"
        f"&what=software+engineer&content-type=application/json"
    )
    data = _http_get_json(url)
    jobs = []
    for j in data.get("results", []):
        title = j.get("title", "")
        if not _is_tech_job(title):
            continue
        jobs.append(
            _norm(
                j.get("id"),
                "adzuna",
                title,
                (j.get("company") or {}).get("display_name"),
                j.get("redirect_url"),
                j.get("description", ""),
                ", ".join((j.get("location") or {}).get("area", [])),
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
    if source == "remotive":
        return fetch_remotive(limit)
    if source == "arbeitnow":  # legacy alias
        return fetch_remotive(limit)
    if source == "jsearch":
        api_key = kwargs.get("api_key") or os_getenv_required("JSEARCH_API_KEY", source)
        query = kwargs.get("query") or os.getenv("JSEARCH_QUERY") or "software engineer India"
        return fetch_jsearch(api_key, query, limit)
    if source == "adzuna":
        app_id = kwargs.get("app_id") or os_getenv_required("ADZUNA_APP_ID", source)
        app_key = kwargs.get("app_key") or os_getenv_required("ADZUNA_APP_KEY", source)
        country = kwargs.get("country") or os.getenv("ADZUNA_COUNTRY") or "in"
        return fetch_adzuna(app_id, app_key, limit, country)
    if source == "fixture":
        return fetch_fixtures(kwargs.get("fixtures_path"), limit)
    raise ValueError(f"Unknown source: {source}")


def fetch_all(limit_per_source: int = 10, sources: Optional[List[str]] = None, **kwargs) -> List[Dict]:
    """Fetch from multiple sources with per-source caps."""
    if not sources:
        # Default: remotive (global remote tech) + remoteok
        # jsearch (OpenWebNinja) is available but excluded from auto-default
        # due to high latency; add explicitly if needed.
        sources = ["remotive", "remoteok"]
        if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"):
            sources.append("adzuna")
        if os.getenv("GREENHOUSE_BOARD_TOKEN"):
            sources.append("greenhouse")
        if os.getenv("LEVER_COMPANY"):
            sources.append("lever")
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