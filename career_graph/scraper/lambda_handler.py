"""EventBridge → Lambda entry point for the job scraper (PRD Layer 2).

Deployable as a Lambda whose trigger is a scheduled EventBridge rule:

    { "limit_per_source": 10, "sources": ["greenhouse", "lever", "remoteok", "arbeitnow"] }

Behavior:
  1. scrape sources (fixture fallback on failure)
  2. send normalized jobs to SQS (stripped HTML) when SQS_QUEUE_URL is set
  3. otherwise persist to /tmp/scrape_<ts>.json so a local worker can consume it
"""
import json
import os
import time

from .pipeline import scrape, jobs_to_sqs, save_scrape


def lambda_handler(event, context=None):
    detail = event.get("detail", event) if isinstance(event, dict) else {}
    limit = int(os.environ.get("SCRAPE_LIMIT_PER_SOURCE", detail.get("limit_per_source", 10)))
    sources = detail.get("sources") or [s for s in os.environ.get("SCRAPE_SOURCES", "").split(",") if s] or None

    jobs = scrape(limit_per_source=limit, sources=sources)

    queue_url = os.environ.get("SQS_QUEUE_URL")
    outcome = {"scraped": len(jobs)}
    if queue_url:
        sent = jobs_to_sqs(jobs, queue_url)
        outcome["queue_url"] = queue_url
        outcome["queued"] = sent
    else:
        path = save_scrape(jobs, f"/tmp/scrape_{int(time.time())}.json")
        outcome["saved"] = path

    print(f"[scraper.lambda] {json.dumps(outcome)}")
    return outcome


if __name__ == "__main__":
    # Useful for local smoke testing: python -m career_graph.scraper.lambda_handler
    print(json.dumps(lambda_handler({"limit_per_source": 5}), indent=2))