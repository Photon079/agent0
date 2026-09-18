import json

import boto3
from moto import mock_aws

from career_graph.ingestion.sqs_consumer_minimal import MinimalSQSConsumer


@mock_aws
def test_minimal_consumer_moto():
    sqs = boto3.resource("sqs", region_name="us-east-1")
    queue = sqs.create_queue(QueueName="test-queue-minimal")
    queue_url = queue.url

    body = json.dumps({"type": "resume", "text": "Name: Proto\nEmail: proto@example.com\nSkills: Python"})
    client = boto3.client("sqs", region_name="us-east-1")
    resp = client.send_message(QueueUrl=queue_url, MessageBody=body)
    assert resp.get("MessageId")

    consumer = MinimalSQSConsumer(queue_url, poll_wait=1, max_messages=1)
    count = consumer.poll_once()
    assert count >= 1
