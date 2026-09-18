"""Job scraper (Greenhouse / Lever / RemoteOK / Arbeitnow + fixtures).

Scrapes job postings, strips HTML, normalizes to a common shape, then either
sends them to SQS (`SQS_QUEUE_URL`) or writes them to a local JSON file that
`scripts/process_jobs.py` can consume.

Example:
    GREENHOUSE_BOARD_TOKEN=stripe LEVER_COMPANY=leverdemo \
        python scripts/run_scraper.py --sources greenhouse lever remoteok --limit 5
"""
import argparse
import json
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.scraper.pipeline import scrape, jobs_to_sqs, save_scrape


def main():
    parser = argparse.ArgumentParser(description="Scrape job postings into SQS or a local file.")
    parser.add_argument("--sources", nargs="+", default=None, choices=["greenhouse", "lever", "remoteok", "arbeitnow", "fixture"])
    parser.add_argument("--limit", type=int, default=10, help="Max jobs per source")
    parser.add_argument("--no-fixtures", action="store_true", help="Do not append fixture jobs")
    parser.add_argument("--out", default="fixtures/scraped/jobs.json", help="Local output file when not using SQS")
    args = parser.parse_args()

    jobs = scrape(limit_per_source=args.limit, sources=args.sources)
    if not args.no_fixtures:
        from career_graph.scraper.sources import fetch_fixtures

        jobs = jobs + fetch_fixtures()

    queue_url = os.environ.get("SQS_QUEUE_URL")
    if queue_url:
        sent = jobs_to_sqs(jobs, queue_url)
        line = f"Sent {sent} jobs to SQS {queue_url}"
    else:
        path = save_scrape(jobs, args.out)
        line = f"Saved {len(jobs)} jobs to {path} (process with: python scripts/process_jobs.py --file {path})"

    print(line)
    for j in jobs[:5]:
        print(f"  - [{j['source']}] {j['title']} @ {j['company']}")


if __name__ == "__main__":
    main()