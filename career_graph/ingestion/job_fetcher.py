import json
import urllib.request
import os
import boto3


s3 = boto3.client("s3")


def fetch_greenhouse_jobs(board_token: str, fixture_s3_key: str = None, timeout: int = 5):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CareerAgent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("jobs", [])
    except Exception:
        # network failure or Cloudflare/rate limit — fall through to S3 fixture
        pass

    if not fixture_s3_key:
        return []

    bucket = os.getenv("FIXTURE_BUCKET", "career-graph-agent-data")
    obj = s3.get_object(Bucket=bucket, Key=fixture_s3_key)
    return json.loads(obj["Body"].read().decode()).get("jobs", [])


def fetch_job_fixtures_local(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("jobs", [])