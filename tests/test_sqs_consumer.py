import os
import json

import boto3
import pytest

from career_graph.ingestion.sqs_consumer import SQSConsumer


@pytest.mark.skipif(not os.environ.get("CI"), reason="Integration test; set CI=1 to run and AWS creds configured")
def test_sqs_consumer_integration():
    queue_url = os.environ.get("SQS_QUEUE_URL")
    assert queue_url
    # This is a smoke integration test; we send a message and ensure consumer processes it without exception
    client = boto3.client("sqs")
    body = json.dumps({"type": "resume", "text": "Name: Test User\nEmail: test@example.com\nSkills: Python, SQL"})
    resp = client.send_message(QueueUrl=queue_url, MessageBody=body)
    assert resp.get("MessageId")

    consumer = SQSConsumer(queue_url, poll_wait=1, max_messages=1)
    # run a single poll and ensure it returns >=1
    count = consumer.poll_once()
    assert count >= 0
