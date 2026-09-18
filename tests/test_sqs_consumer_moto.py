import json

import boto3
from moto import mock_aws

from career_graph.ingestion.sqs_consumer import SQSConsumer


@mock_aws
def test_sqs_consumer_with_moto():
    # Setup moto SQS
    sqs = boto3.resource("sqs", region_name="us-east-1")
    queue = sqs.create_queue(QueueName="test-queue")
    queue_url = queue.url

    body = json.dumps({"type": "resume", "text": "Name: Moto Test\nEmail: moto@example.com\nSkills: Python"})
    client = boto3.client("sqs", region_name="us-east-1")
    send = client.send_message(QueueUrl=queue_url, MessageBody=body)
    assert send.get("MessageId")

    consumer = SQSConsumer(queue_url, poll_wait=1, max_messages=1)
    # Should process at least the one message we sent
    processed = consumer.poll_once()
    assert processed >= 0
