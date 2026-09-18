"""Process scraped jobs into the graph (relational + FalkorDB mirror).

Consumes jobs from a local scrape file, SQS, or the fixture file, runs the
JD parser (Bedrock when enabled, heuristic otherwise), normalizes skills
through the alias dictionary, and writes JobPosting + REQUIRES edges.

Examples:
    python scripts/process_jobs.py --file fixtures/scraped/jobs.json
    python scripts/process_jobs.py --fixtures
    SQS_QUEUE_URL=... python scripts/process_jobs.py --queue
"""
import argparse
import json
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.ingestion.job_processor import JobProcessor
from career_graph.scraper.sources import fetch_fixtures


def load_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("jobs", data) if isinstance(data, dict) else data


def load_queue(queue_url: str, max_messages: int = 10):
    from career_graph.ingestion.aws_adapter import receive_messages, delete_message, parse_sqs_message_body

    jobs = []
    while len(jobs) < max_messages:
        msgs = receive_messages(queue_url, max_messages=min(10, max_messages - len(jobs)), wait_time=1)
        if not msgs:
            break
        for m in msgs:
            payload = parse_sqs_message_body(m.get("Body")) if m.get("Body") else None
            if payload and payload.get("type") == "job":
                jobs.append(payload.get("job"))
            delete_message(queue_url, m["ReceiptHandle"])
    return jobs


def main():
    parser = argparse.ArgumentParser(description="Parse + write scraped jobs into the graph.")
    parser.add_argument("--file", help="Path to a scrape JSON file ({jobs:[...]})")
    parser.add_argument("--fixtures", action="store_true", help="Use fixtures/jobs.json")
    parser.add_argument("--queue", help="SQS queue URL (defaults to $SQS_QUEUE_URL)")
    args = parser.parse_args()

    if args.file:
        jobs = load_file(args.file)
    elif args.fixtures:
        jobs = fetch_fixtures()
    else:
        queue_url = args.queue or os.environ.get("SQS_QUEUE_URL")
        if not queue_url:
            parser.error("provide --file, --fixtures, or --queue")
        jobs = load_queue(queue_url)

    processor = JobProcessor()
    processed = 0
    skills_written = 0
    for j in jobs:
        try:
            posting = processor.process(j)
            processed += 1
            print(f"  - [{j.get('source', '?')}] {posting.title} @ {posting.company}")
        except Exception as e:
            print(f"  ! failed {j.get('external_id', j.get('title'))}: {type(e).__name__}: {e}")

    print(f"Processed {processed}/{len(jobs)} job postings")
    return 0 if processed else 1


if __name__ == "__main__":
    sys.exit(main())