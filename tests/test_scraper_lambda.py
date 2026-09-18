"""Tests for the EventBridge Lambda handler and the scraper->SQS pipeline."""
import json

import boto3
from moto import mock_aws

from career_graph.scraper import lambda_handler
from career_graph.scraper.pipeline import jobs_to_sqs


def test_lambda_handler_scrapes_and_saves(monkeypatch, tmp_path):
    def fake_scrape(limit_per_source=10, sources=None, **kw):
        return [{"external_id": "remoteok:1", "source": "remoteok", "title": "DevOps", "company": "Acme", "url": "x", "description": "Kubernetes"}]

    monkeypatch.setattr(lambda_handler, "scrape", fake_scrape)
    monkeypatch.setattr(lambda_handler, "save_scrape", lambda jobs, path: path)
    out = lambda_handler.lambda_handler({"limit_per_source": 5})
    assert out["scraped"] == 1


@mock_aws
def test_jobs_to_sqs_messages():
    from career_graph.ingestion.aws_adapter import receive_messages

    sqs = boto3.resource("sqs", region_name="us-east-1")
    queue = sqs.create_queue(QueueName="scrape-queue")
    jobs = [{"external_id": "greenhouse:1", "source": "greenhouse", "title": "SWE", "company": "Stripe", "url": "https://x/1", "description": "<p>Python</p>"}]
    sent = jobs_to_sqs(jobs, queue.url)
    assert sent == 1

    msgs = receive_messages(queue.url, max_messages=1, wait_time=1)
    assert len(msgs) == 1
    payload = json.loads(msgs[0]["Body"])
    assert payload["type"] == "job"
    assert payload["job"]["title"] == "SWE"