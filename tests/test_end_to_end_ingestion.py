import json

import boto3
from moto import mock_aws

from career_graph.ingestion.sqs_consumer_minimal import MinimalSQSConsumer
from career_graph.db import get_session
from career_graph.models import Candidate, Skill


@mock_aws
def test_resume_message_end_to_end():
    sqs = boto3.resource("sqs", region_name="us-east-1")
    queue = sqs.create_queue(QueueName="e2e-queue")
    queue_url = queue.url

    body = json.dumps({"type": "resume", "text": "John Doe\njohn@example.com\nSkills: Python, SQL"})
    client = boto3.client("sqs", region_name="us-east-1")
    resp = client.send_message(QueueUrl=queue_url, MessageBody=body)
    assert resp.get("MessageId")

    consumer = MinimalSQSConsumer(queue_url, poll_wait=1, max_messages=1)
    n = consumer.poll_once()
    assert n >= 1

    # verify DB entries
    with get_session() as session:
        cand = session.query(Candidate).filter(Candidate.email == "john@example.com").first()
        assert cand is not None
        # skill normalized to Python exists
        sk = session.query(Skill).filter(Skill.canonical_name == "Python").first()
        assert sk is not None
