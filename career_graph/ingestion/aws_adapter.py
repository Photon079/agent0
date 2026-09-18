"""AWS adapters for SQS and S3 used by the SQS consumer.

Requires `boto3` and proper AWS credentials in environment or IAM role.
"""
import json
import logging
from typing import List, Optional

import boto3
import os

log = logging.getLogger(__name__)


def get_sqs_client():
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    return boto3.client("sqs", region_name=region)


def get_s3_client():
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    return boto3.client("s3", region_name=region)


def receive_messages(queue_url: str, max_messages: int = 10, wait_time: int = 20):
    client = get_sqs_client()
    resp = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_time,
        MessageAttributeNames=["All"],
        AttributeNames=["ApproximateReceiveCount"],
    )
    return resp.get("Messages", [])


def delete_message(queue_url: str, receipt_handle: str):
    client = get_sqs_client()
    client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


def change_message_visibility(queue_url: str, receipt_handle: str, visibility_timeout: int):
    client = get_sqs_client()
    client.change_message_visibility(QueueUrl=queue_url, ReceiptHandle=receipt_handle, VisibilityTimeout=visibility_timeout)


def send_message(queue_url: str, body: str, message_attributes: dict | None = None):
    client = get_sqs_client()
    params = {"QueueUrl": queue_url, "MessageBody": body}
    if message_attributes:
        params["MessageAttributes"] = message_attributes
    return client.send_message(**params)


def download_s3_text(bucket: str, key: str) -> Optional[str]:
    client = get_s3_client()
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        return data.decode("utf-8")
    except Exception as e:
        log.exception("Failed to download s3://%s/%s: %s", bucket, key, e)
        return None


def parse_sqs_message_body(msg_body: str):
    """Try to parse JSON body and return dict, or None."""
    try:
        return json.loads(msg_body)
    except Exception:
        return None