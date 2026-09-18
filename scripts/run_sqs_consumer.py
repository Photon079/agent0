"""Run the SQS consumer (requires AWS credentials and an existing queue).

Usage: set `SQS_QUEUE_URL` environment variable and run this script.
"""

import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
# Repo root goes on sys.path so the career_graph package is importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
from career_graph.ingestion.sqs_consumer import SQSConsumer


def main():
    queue_url = os.environ.get("SQS_QUEUE_URL")
    if not queue_url:
        raise SystemExit("Set SQS_QUEUE_URL environment variable to an SQS queue URL")
    dlq = os.environ.get("SQS_DLQ_URL")
    dlq_threshold = int(os.environ.get("SQS_DLQ_THRESHOLD", "5"))
    # optional metrics port
    metrics_port = int(os.environ.get("METRICS_PORT", "0") or 0)
    consumer = SQSConsumer(queue_url, dlq_queue_url=dlq, dlq_threshold=dlq_threshold)
    consumer.run()


if __name__ == "__main__":
    main()