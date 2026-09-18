"""Minimal single-threaded SQS consumer for local prototyping.

This consumer is intentionally simple: it polls messages, parses them
with existing parsers, writes to the graph using `GraphWriter`, and
deletes messages. It also mirrors writes into FalkorDB when available.
No DLQ, no metrics, no concurrency — easy to run locally.
"""
import logging
import time
from typing import Dict

from .aws_adapter import receive_messages, delete_message, parse_sqs_message_body, download_s3_text
from ..graph_writer import GraphWriter

log = logging.getLogger(__name__)


class MinimalSQSConsumer:
    def __init__(self, queue_url: str, poll_wait: int = 5, max_messages: int = 1):
        self.queue_url = queue_url
        self.poll_wait = poll_wait
        self.max_messages = max_messages
        self.gw = GraphWriter()

    def _handle_payload(self, payload: Dict):
        from .job_processor import JobProcessor
        from .candidate_ingestor import CandidateIngestor

        ingestor = CandidateIngestor()
        t = payload.get("type")
        if t == "resume":
            if payload.get("s3_bucket") and payload.get("s3_key"):
                text = download_s3_text(payload["s3_bucket"], payload["s3_key"])
            else:
                text = payload.get("text", "")
            return ingestor.ingest_resume_text(text)

        if t == "github":
            return ingestor.ingest_github_repos(
                payload.get("repos", []),
                name=payload.get("name"),
                email=payload.get("email"),
            )

        if t == "job":
            job = payload.get("job") or {"title": None, "description": payload.get("text", "")}
            return JobProcessor().process(job)

        log.warning("Unknown message type: %s", t)
        return None

    def poll_once(self):
        msgs = receive_messages(self.queue_url, max_messages=self.max_messages, wait_time=self.poll_wait)
        if not msgs:
            return 0
        count = 0
        for m in msgs:
            body = m.get("Body")
            receipt = m.get("ReceiptHandle")
            payload = parse_sqs_message_body(body) if body else None
            try:
                if payload:
                    self._handle_payload(payload)
                else:
                    log.warning("Non-json message received; deleting")
                delete_message(self.queue_url, receipt)
            except Exception:
                log.exception("Failed to process message")
            count += 1
        return count

    def run(self):
        log.info("Starting minimal SQS consumer for %s", self.queue_url)
        try:
            while True:
                n = self.poll_once()
                if n == 0:
                    time.sleep(1)
        except KeyboardInterrupt:
            log.info("Minimal consumer stopped")