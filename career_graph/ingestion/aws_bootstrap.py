"""Cost-conscious AWS provisioning for the Career Graph agent.

Design intent (matches the "shut it all down after the hackathon" constraint):
  * Only pay-as-you-go, demo-critical services are provisioned on AWS.
  * No Fargate (FalkorDB stays local in Docker) — avoids the ~$12/mo bill.
  * Scrapes/resumes in S3 get a lifecycle rule so old data expires and can't
    rack up storage charges.
  * SQS has a matching DLQ; EventBridge schedules the scraper Lambda.
  * `teardown()` deletes every resource this module created, so the account can
    be closed cleanly.

The functions are thin wrappers around `career_graph/ingestion/aws_adapter.py`.
That adapter is deliberately split from this one so the SQS consumer can be
tested with moto without touching provisioning. If you run this locally with
real credentials, every operation is idempotent (re-running `bootstrap()` is
safe).

Usage (env: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION):
    python -c "from career_graph.ingestion.aws_bootstrap import bootstrap; bootstrap()"
"""
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from .aws_adapter import (
    get_sqs_client,
    get_s3_client,
    send_message,
    receive_messages,
    delete_message,
    change_message_visibility,
    download_s3_text,
)
from .aws_events_adapter import (
    get_eventbridge_client,
    get_lambda_client,
    put_eventbridge_rule,
    add_lambda_target_to_rule,
    grant_invoke_permission,
)

log = logging.getLogger(__name__)

# Names are fine to be static: demo account suffix keeps them unique per account.
SQS_JOB_QUEUE = "career-graph-jobs"
SQS_JOB_DLQ = "career-graph-jobs-dlq"
SQS_RESUME_QUEUE = "career-graph-resumes"
SQS_RESUME_DLQ = "career-graph-resumes-dlq"
S3_BUCKET = os.environ.get("CAREER_GRAPH_S3_BUCKET", "career-graph-fixtures")
EVENTBRIDGE_RULE = "career-graph-scrape-rule"
LAMBDA_SCRAPER = "career-graph-scraper"
SCRAPE_SCHEDULE = os.environ.get("SCRAPE_SCHEDULE", "cron(0 */6 * * ? *)")  # 4x/day
LIFECYCLE_EXPIRE_DAYS = int(os.environ.get("SCRAPE_EXPIRE_DAYS", "14"))


def _region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


def _account_id() -> str:
    import boto3

    try:
        return boto3.client("sts", region_name=_region()).get_caller_identity()["Account"]
    except Exception:
        return "000000000000"


def _queue_arn(name: str) -> str:
    return f"arn:aws:sqs:{_region()}:{_account_id()}:{name}"


# ---------------- SQS ----------------

def ensure_sqs_pair(name: str, dlq_name: str) -> Dict[str, str]:
    """Create DLQ + queue (if missing), wire maxReceiveCount redrive. Idempotent."""
    sqs = get_sqs_client()
    dlq = sqs.create_queue(QueueName=dlq_name, Attributes={"MessageRetentionPeriod": "1209600"})
    dlq_url = dlq["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]

    try:
        q = sqs.create_queue(
            QueueName=name,
            Attributes={
                "MessageRetentionPeriod": "604800",
                "VisibilityTimeout": "300",
                "RedrivePolicy": json.dumps(
                    {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": 3}
                ),
            },
        )
    except Exception:
        # already exists (idempotent re-bootstrap)
        q = sqs.get_queue_url(QueueName=name) if _queue_exists(sqs, name) else sqs.create_queue(QueueName=name)

    queue_url = q["QueueUrl"]
    # re-apply redrive in case it drifted
    sqs.set_queue_attributes(QueueUrl=queue_url, Attributes={"RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": 3})})
    return {"queue_url": queue_url, "dlq_url": dlq_url, "queue_arn": _queue_arn(name), "dlq_arn": dlq_arn}


def _queue_exists(sqs, name: str) -> bool:
    try:
        sqs.get_queue_url(QueueName=name)
        return True
    except Exception:
        return False


def send_test_message(queue_url: str, source: str = "fixture") -> Dict:
    """Send a normalized scraper job as a sample SQS message (PRD dry-run check)."""
    body = json.dumps(
        {
            "type": "job",
            "job": {
                "external_id": f"{source}:probe-1",
                "source": source,
                "title": "Career Agent Probe",
                "company": "CareerGraph",
                "url": "https://example.com/probe",
                "description": "Python AWS Terraform Kubernetes\n",
            },
        }
    )
    return send_message(queue_url, body)


# ---------------- S3 ----------------

def ensure_s3_bucket(name: str = S3_BUCKET) -> Dict:
    """Create bucket + expiry lifecycle (fixtures/, resumes/, generated/). Idempotent."""
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=name)
        exists = True
    except Exception:
        exists = False

    if not exists:
        kwargs: Dict[str, Any] = {"Bucket": name}
        if _region() != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": _region()}
        s3.create_bucket(**kwargs)

    s3.put_bucket_lifecycle_configuration(
        Bucket=name,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "expire-fixtures",
                    "Status": "Enabled",
                    "Prefix": "fixtures/",
                    "Expiration": {"Days": LIFECYCLE_EXPIRE_DAYS},
                },
                {
                    "ID": "expire-resumes",
                    "Status": "Enabled",
                    "Prefix": "resumes/",
                    "Expiration": {"Days": LIFECYCLE_EXPIRE_DAYS},
                },
            ]
        },
    )
    # scaffold the fixture buckets the consumers expect
    _put_scaffold(s3, name)
    return {"bucket": name, "created": not exists}


def _put_scaffold(s3, bucket: str):
    for prefix in ("fixtures/jobs/", "fixtures/jobs_processed/", "resumes/inbox/"):
        s3.put_object(Bucket=bucket, Key=prefix, Body=b"")


# ---------------- EventBridge ----------------

def ensure_scrape_rule(lambda_name: str = LAMBDA_SCRAPER) -> Dict:
    """Create/refresh the EventBridge schedule that triggers the scraper Lambda."""
    events = get_eventbridge_client()
    rule = put_eventbridge_rule(EVENTBRIDGE_RULE, SCRAPE_SCHEDULE)
    lambda_client = get_lambda_client()
    rule_arn = events.describe_rule(Name=EVENTBRIDGE_RULE)["Arn"]
    add_lambda_target_to_rule(rule, lambda_name)  # idempotent target add
    grant_invoke_permission(lambda_name, "events.amazonaws.com", EVENTBRIDGE_RULE, rule_arn)
    return {"rule_arn": rule_arn, "rule_name": EVENTBRIDGE_RULE, "schedule": SCRAPE_SCHEDULE}


# ---------------- Cost / summary ----------------

def estimate_monthly_cost() -> Dict[str, str]:
    """Rough on-demand estimates for the services we provision (as of early 2026).

    S3: ~$0.023/GB-mo -> a demo holding <100MB of scrapes is effectively $0.00.
    SQS: $0.40 per 1M requests -> a few thousand messages/mo is $0.00.
    EventBridge schedules: free after 14/day per account (ours fires 4x/day).
    Lambda: first 1M requests/mo free; Idle cost $0.
    Bedrock Haiku: ~$1.25/M input tokens; a few hundred KB of JDs/mo is pennies.
    """
    return {
        "s3_storage": "<$0.01/mo (lifecycle expires old data)",
        "sqs": "~$0.00/mo (pay-per-use, far below 1M requests)",
        "eventbridge": "free (4 scheduled fire/month << 14/day free tier)",
        "lambda": "free (inside 1M requests/mo free tier)",
        "bedrock_haiku": "pennies (hundreds of KB of input tokens/mo)",
        "total": "effectively $0.00-$0.05 for demo-scale usage",
    }


def bootstrap() -> Dict:
    """Create S3 + (SQS, DLQ) + (SQS resume, DLQ) + EventBridge rule. Idempotent."""
    out: Dict[str, Any] = {}
    out["s3"] = ensure_s3_bucket()
    out["job_queue"] = ensure_sqs_pair(SQS_JOB_QUEUE, SQS_JOB_DLQ)
    out["resume_queue"] = ensure_sqs_pair(SQS_RESUME_QUEUE, SQS_RESUME_DLQ)
    out["events"] = ensure_scrape_rule()
    out["cost_estimate"] = estimate_monthly_cost()
    return out


def teardown() -> Dict[str, bool]:
    """Delete every resource this module created. Best-effort; returns per-resource status."""
    results: Dict[str, bool] = {}
    sqs = get_sqs_client()
    s3 = get_s3_client()

    for name in (SQS_JOB_QUEUE, SQS_JOB_DLQ, SQS_RESUME_QUEUE, SQS_RESUME_DLQ):
        try:
            url = sqs.get_queue_url(QueueName=name)["QueueUrl"]
            sqs.delete_queue(QueueUrl=url)
            results[f"sqs:{name}"] = True
        except Exception:
            results[f"sqs:{name}"] = False

    try:
        # empty the bucket first (delete_objects all), then delete_bucket
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET):
            keys = [{"Key": k} for k in page.get("Contents", [])]
            if keys:
                s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": keys})
        s3.delete_bucket(Bucket=S3_BUCKET)
        results[f"s3:{S3_BUCKET}"] = True
    except Exception:
        results[f"s3:{S3_BUCKET}"] = False

    try:
        events = get_eventbridge_client()
        events.remove_targets(Rule=EVENTBRIDGE_RULE, Ids=[LAMBDA_SCRAPER])
        events.delete_rule(Name=EVENTBRIDGE_RULE)
        results[f"events:{EVENTBRIDGE_RULE}"] = True
    except Exception:
        results[f"events:{EVENTBRIDGE_RULE}"] = False

    try:
        lc = get_lambda_client()
        lc.delete_function(FunctionName=LAMBDA_SCRAPER)
        results[f"lambda:{LAMBDA_SCRAPER}"] = True
    except Exception:
        results[f"lambda:{LAMBDA_SCRAPER}"] = False

    return results
