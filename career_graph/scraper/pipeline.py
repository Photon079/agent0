"""Scraper pipeline: fetch jobs from multiple sources, optionally send to SQS.

Matches the PRD flow: EventBridge → Scraper (sources + fixture fallback) → SQS,
where the SQS message body is a stripped, normalized JSON job payload.
The consumer side (JobProcessor) is what parses skills and writes the graph.
"""
import json
import os
from typing import Dict, List, Optional

from .sources import fetch_all, fetch_source

__all__ = ["scrape", "jobs_to_sqs", "save_scrape", "load_scrape"]


def scrape(limit_per_source: int = 10, sources: Optional[List[str]] = None, **kwargs) -> List[Dict]:
    """Fetch jobs from the configured sources (with per-source caps)."""
    if sources == ["fixture"]:
        return fetch_source("fixture", limit_per_source, **kwargs)
    return fetch_all(limit_per_source, sources, **kwargs)


def jobs_to_sqs(jobs: List[Dict], queue_url: str) -> int:
    """Send normalized jobs to SQS as `{"type": "job", "job": {...}}` messages."""
    from ..ingestion.aws_adapter import send_message

    sent = 0
    for j in jobs:
        body = json.dumps({"type": "job", "job": j})
        send_message(queue_url, body)
        sent += 1
    return sent


def save_scrape(jobs: List[Dict], path: str) -> str:
    """Persist a scrape to JSON (S3-style bucket/object stand-in for local runs)."""
    payload = {"jobs": jobs}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def load_scrape(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("jobs", [])