"""SQS consumer that polls an SQS queue and processes messages into the GraphWriter.

Features:
- concurrent workers (ThreadPoolExecutor)
- exponential backoff via ChangeMessageVisibility
- optional DLQ move after threshold
- optional mirroring into FalkorDB (best-effort)
- Prometheus metrics (optional HTTP server via METRICS_PORT)
- graceful shutdown on SIGINT/SIGTERM
"""
import logging
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

from prometheus_client import Counter, Histogram, Gauge, start_http_server

from .aws_adapter import (
    receive_messages,
    delete_message,
    parse_sqs_message_body,
    download_s3_text,
    change_message_visibility,
    send_message,
)
from ..graph_writer import GraphWriter

log = logging.getLogger(__name__)

# Prometheus metrics
PROCESSED_COUNTER = Counter("career_graph_sqs_processed_total", "Total SQS messages processed")
FAILED_COUNTER = Counter("career_graph_sqs_failed_total", "Total SQS messages failed processing")
DLQ_COUNTER = Counter("career_graph_sqs_dlq_total", "Total messages moved to DLQ")
PROCESS_HIST = Histogram("career_graph_sqs_processing_seconds", "Message processing time seconds")
IN_FLIGHT = Gauge("career_graph_sqs_in_flight", "Number of messages currently being processed")


class SQSConsumer:
    def __init__(
        self,
        queue_url: str,
        poll_wait: int = 20,
        max_messages: int = 10,
        backoff_base: int = 5,
        backoff_max: int = 300,
        max_workers: int = 4,
        dlq_queue_url: Optional[str] = None,
        dlq_threshold: int = 5,
    ):
        self.queue_url = queue_url
        self.poll_wait = poll_wait
        self.max_messages = max_messages
        self.gw = GraphWriter()
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.dlq_queue_url = dlq_queue_url
        self.dlq_threshold = dlq_threshold

        metrics_port = int(os.environ.get("METRICS_PORT", "0") or 0)
        if metrics_port:
            try:
                start_http_server(metrics_port)
                log.info("Prometheus metrics exposed on port %s", metrics_port)
            except Exception:
                log.exception("Failed to start metrics HTTP server")

        self._stop = False

    def _process_message(self, m: Dict[str, Any]):
        """Process a single SQS message dict. Returns (success: bool, receipt_handle, approx_receive_count)."""
        body = m.get("Body")
        receipt = m.get("ReceiptHandle")
        attrs = m.get("Attributes", {}) or {}
        approx = int(attrs.get("ApproximateReceiveCount", "1"))
        payload = parse_sqs_message_body(body) if body else None

        if not payload:
            log.warning("Skipping non-json message")
            try:
                delete_message(self.queue_url, receipt)
            except Exception:
                log.exception("Failed to delete non-json message")
            PROCESSED_COUNTER.inc()
            return True, receipt, approx

        IN_FLIGHT.inc()
        with PROCESS_HIST.time():
            try:
                from .job_processor import JobProcessor
                from .candidate_ingestor import CandidateIngestor

                ingestor = CandidateIngestor()
                t = payload.get("type")
                if t == "resume":
                    if payload.get("s3_bucket") and payload.get("s3_key"):
                        text = download_s3_text(payload["s3_bucket"], payload["s3_key"])
                    else:
                        text = payload.get("text", "")
                    cand = ingestor.ingest_resume_text(text)
                    log.info("Wrote candidate %s", getattr(cand, "id", None))

                elif t == "github":
                    candidate = ingestor.ingest_github_repos(
                        payload.get("repos", []),
                        name=payload.get("name"),
                        email=payload.get("email"),
                    )
                    log.info("Wrote candidate %s from github", getattr(candidate, "id", None))

                elif t == "job":
                    job = payload.get("job") or {"title": None, "description": payload.get("text", "")}
                    posting = JobProcessor().process(job)
                    log.info("Wrote job posting %s (%s requirements)", getattr(posting, "id", None), len(payload.get("job", {}).get("requirements", [])))

                else:
                    log.warning("Unknown message type: %s", t)

                # on success, delete
                try:
                    delete_message(self.queue_url, receipt)
                except Exception:
                    log.exception("Failed to delete message after success")
                PROCESSED_COUNTER.inc()
                return True, receipt, approx

            except Exception:
                log.exception("Failed processing message")
                FAILED_COUNTER.inc()
                return False, receipt, approx
            finally:
                IN_FLIGHT.dec()

    def poll_once(self):
        msgs = receive_messages(self.queue_url, max_messages=self.max_messages, wait_time=self.poll_wait)
        if not msgs:
            return 0

        futures = {self.executor.submit(self._process_message, m): m for m in msgs}
        processed = 0
        for fut in as_completed(futures):
            success, receipt, approx = fut.result()
            if not success:
                # if exceed DLQ threshold, move to DLQ if configured
                if self.dlq_queue_url and approx >= self.dlq_threshold:
                    try:
                        original = futures[fut]
                        body = original.get("Body")
                        send_message(self.dlq_queue_url, body or "")
                        delete_message(self.queue_url, receipt)
                        log.info("Moved message to DLQ %s", self.dlq_queue_url)
                        DLQ_COUNTER.inc()
                        processed += 1
                        continue
                    except Exception:
                        log.exception("Failed to move message to DLQ")
                try:
                    delay = min(self.backoff_base * (2 ** (max(0, approx - 1))), self.backoff_max)
                    change_message_visibility(self.queue_url, receipt, int(delay))
                    log.info("Set visibility timeout to %s seconds for receipt %s", delay, receipt)
                except Exception:
                    log.exception("Failed to set visibility timeout")
            processed += 1

        return processed

    def run(self):
        """Start polling loop. Handles graceful shutdown on signals."""

        def _handle_sig(signum, frame):
            log.info("Received shutdown signal %s", signum)
            self._stop = True

        signal.signal(signal.SIGINT, _handle_sig)
        signal.signal(signal.SIGTERM, _handle_sig)

        log.info("Starting SQS consumer for %s", self.queue_url)
        try:
            while not self._stop:
                count = self.poll_once()
                if count == 0:
                    time.sleep(1)
        finally:
            log.info("Shutting down executor")
            self.executor.shutdown(wait=True)