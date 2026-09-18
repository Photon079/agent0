"""Run the minimal SQS consumer (prototype). Set `SQS_QUEUE_URL` and run."""
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.ingestion.sqs_consumer_minimal import MinimalSQSConsumer


def main():
    queue_url = os.environ.get("SQS_QUEUE_URL")
    if not queue_url:
        raise SystemExit("Set SQS_QUEUE_URL environment variable to an SQS queue URL")
    consumer = MinimalSQSConsumer(queue_url)
    consumer.run()


if __name__ == "__main__":
    main()