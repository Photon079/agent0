"""EventBridge + Lambda adapters for the Career Graph AWS bootstrap.

Thin, cost-conscious, idempotent wrappers around boto3 ``events`` and ``lambda``.
This adapter is split from ``aws_adapter.py`` so provisioning logic
(``aws_bootstrap.py``) can touch EventBridge/Lambda without forcing the SQS
consumer to depend on them, and both halves stay testable with moto.

Design intent (matches the "shut it all down after the hackathon" constraint):
  * Only pay-as-you-go, demo-critical resources are created: one scheduled
    EventBridge rule that fires the scraper Lambda a handful of times a day.
    No Fargate, no always-on services.
  * Every function is a thin pass-through (real API calls when run with real
    credentials) and is idempotent — re-running ``bootstrap()`` is safe.
  * ``grant_invoke_permission`` only adds the invoke permission if the matching
    statement isn't already present, so re-bootstrapping never accumulates
    duplicate statements.

If you run this locally with real credentials, these hit AWS directly.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


def _account_id() -> str:
    import boto3

    try:
        return boto3.client("sts", region_name=_region()).get_caller_identity()["Account"]
    except Exception:
        return "000000000000"


def _lambda_arn(name: str) -> str:
    return f"arn:aws:lambda:{_region()}:{_account_id()}:function:{name}"


# ---------------- clients ----------------

def get_eventbridge_client():
    import boto3

    return boto3.client("events", region_name=_region())


def get_lambda_client():
    import boto3

    return boto3.client("lambda", region_name=_region())


# ---------------- EventBridge rule ----------------

def put_eventbridge_rule(rule_name: str, schedule_expression: str) -> Dict[str, str]:
    """Create/refresh a scheduled EventBridge rule. Idempotent.

    ``schedule_expression`` is an EventBridge rate/cron expression, e.g.
    ``"cron(0 */6 * * ? *)"``. Returns a summary dict (used downstream by
    ``add_lambda_target_to_rule``).
    """
    events = get_eventbridge_client()
    events.put_rule(Name=rule_name, ScheduleExpression=schedule_expression, State="ENABLED")
    rule_arn = events.describe_rule(Name=rule_name)["Arn"]
    return {"rule_name": rule_name, "schedule": schedule_expression, "rule_arn": rule_arn}


def add_lambda_target_to_rule(rule: Dict[str, str], lambda_name: str) -> Dict[str, str]:
    """Idempotently attach ``lambda_name`` as a target of ``rule``.

    ``rule`` is the dict returned by ``put_eventbridge_rule``. Existing targets
    are read first so re-bootstrapping never creates duplicates.
    """
    events = get_eventbridge_client()
    rule_name = rule["rule_name"]
    target_id = f"{lambda_name}-target"

    existing = events.list_targets_by_rule(Rule=rule_name).get("Targets", [])
    if not any(t.get("Id") == target_id for t in existing):
        events.put_targets(
            Rule=rule_name,
            Targets=[{"Id": target_id, "Arn": _lambda_arn(lambda_name)}],
        )
    return {"rule_name": rule_name, "lambda_name": lambda_name, "target_id": target_id}


def grant_invoke_permission(lambda_name: str, source: str, rule_name: str, rule_arn: str) -> Dict[str, str]:
    """Allow EventBridge to invoke the scraper Lambda. Idempotent.

    Only adds the statement if it isn't already present, so re-running
    ``bootstrap()`` never accumulates duplicate invoke permissions.
    """
    lc = get_lambda_client()
    statement_id = f"{rule_name}-invoke"

    try:
        policy = json.loads(lc.get_policy(FunctionName=lambda_name).get("Policy", "{}"))
        if any(s.get("Sid") == statement_id for s in policy.get("Statement", [])):
            return {"statement_id": statement_id, "already_present": True, "lambda_name": lambda_name}
    except Exception:
        pass  # no policy yet -> add it below

    lc.add_permission(
        FunctionName=lambda_name,
        StatementId=statement_id,
        Action="lambda:InvokeFunction",
        Principal=source,
        SourceArn=rule_arn,
    )
    return {"statement_id": statement_id, "already_present": False, "lambda_name": lambda_name}
