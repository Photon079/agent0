"""Bedrock (Claude Haiku) extraction with deterministic heuristic fallback.

Every public function in this module:
  - returns the same shape regardless of whether Bedrock is used, and
  - falls back to the heuristic parsers on any error (no credentials, model
    unavailable, malformed JSON, invalid schema, timeout).

Enable Bedrock with env `CAREER_GRAPH_USE_BEDROCK=1`.
"""
import json
import os
import re
from typing import Any, Dict, List

USE_BEDROCK = os.environ.get("CAREER_GRAPH_USE_BEDROCK", "").lower() in ("1", "true", "yes")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
RESUME_MODEL = os.environ.get("BEDROCK_RESUME_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0")
JD_MODEL = os.environ.get("BEDROCK_JD_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0")
GITHUB_MODEL = os.environ.get("BEDROCK_GITHUB_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0")

_JSON_BLOCK_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def _converse(system: str, user: str, model: str, max_tokens: int = 2048) -> str:
    import boto3  # lazy import: only shipped here so tests never need creds

    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    resp = client.converse(
        modelId=model,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
    )
    return resp["output"]["message"]["content"][0]["text"]


def _parse_json_text(text: str) -> Any:
    """Extract the first JSON value from a model response (ignores prose)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if match:
            return json.loads(match.group(0))
        raise


def _require_json(value):
    if isinstance(value, dict):
        return value
    raise ValueError("model returned invalid JSON shape")


# ---------------- Resume ----------------

def _bedrock_resume(text: str) -> Dict[str, Any]:
    system = (
        "You extract structured data from software-engineering resumes. "
        'Return ONLY valid JSON with keys "name", "email" (string or null), '
        '"skills" (array of {"name","confidence","evidence"}) and '
        '"projects" (array of {"name","description","url"}). Use exact skill '
        'names from the text (e.g. "TypeScript", "AWS").'
    )
    user = f"<resume>\n{text[:12000]}\n</resume>"
    raw = _converse(system, user, RESUME_MODEL)
    data = _require_json(_parse_json_text(raw))
    return {
        "name": str(data.get("name") or "Unknown"),
        "email": (data.get("email") or None),
        "skills": data.get("skills", []),
        "projects": data.get("projects", []),
    }


def extract_resume(text: str) -> Dict[str, Any]:
    if USE_BEDROCK and text.strip():
        try:
            return _bedrock_resume(text)
        except Exception:
            if os.environ.get("BEDROCK_DEBUG"):
                import traceback

                traceback.print_exc()
    from ..normalizer.alias_normalizer import AliasNormalizer
    from ..parsers.simple_resume_parser import SimpleResumeParser

    normalizer = AliasNormalizer()
    parsed = SimpleResumeParser().parse(text)
    for s in parsed.get("skills", []):
        s["canonical_name"] = normalizer.normalize(s.get("canonical_name") or s.get("name") or "")
    return parsed


# ---------------- Job descriptions ----------------

def _bedrock_job_skills(description: str, title: str) -> Dict[str, Any]:
    system = (
        "You extract required skills from software job descriptions. Return "
        'ONLY valid JSON: {"skills":[{"name":"Python","importance":1.0}]}. '
        "importance is the weight of the requirement (1.0 = required, "
        "0.5 = nice-to-have, 0.2 = rare mention). Deduplicate skills."
    )
    user = f"<job title=\"{title}\">\n{description[:12000]}\n</job>"
    raw = _converse(system, user, JD_MODEL)
    data = _require_json(_parse_json_text(raw))
    return {"skills": data.get("skills", [])}


def extract_job_skills(description: str, title: str = "") -> Dict[str, Any]:
    if USE_BEDROCK and description.strip():
        try:
            return _bedrock_job_skills(description, title)
        except Exception:
            if os.environ.get("BEDROCK_DEBUG"):
                import traceback

                traceback.print_exc()
    from ..normalizer.alias_normalizer import AliasNormalizer
    from ..parsers.job_parser import JobParser

    normalizer = AliasNormalizer()
    parsed = JobParser().parse(description)
    for s in parsed.get("skills", []):
        s["canonical_name"] = normalizer.normalize(s.get("canonical_name") or s.get("name") or "")
    return {"skills": parsed.get("skills", [])}


# ---------------- GitHub repos ----------------

def _bedrock_github_repos(repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    from ..parsers.github_parser import GithubParser

    base = GithubParser().parse(repos)
    with_readme = [r for r in repos if (r.get("readme_text") or "").strip()]
    if not with_readme:
        return base

    system = (
        "For each GitHub repository, infer the tech skills shown in its "
        'README. Return ONLY valid JSON: {"repos":{"repo_name":["Python","AWS"]}}. '
        "Use exact, canonical skill names."
    )
    user = "\n\n".join(
        f"<repo name={r.get('name')}>\n{(r.get('readme_text') or '')[:4000]}\n</repo>"
        for r in with_readme[:10]
    )
    raw = _converse(system, user, GITHUB_MODEL)
    data = _require_json(_parse_json_text(raw))
    by_name = data.get("repos", {})
    for proj in base.get("projects", []):
        tagged = by_name.get(proj.get("name")) or []
        proj["skills"] = list(dict.fromkeys(list(proj.get("skills", [])) + [s for s in tagged if s]))
    return base


def extract_github_repos(repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    if USE_BEDROCK and repos:
        try:
            return _bedrock_github_repos(repos)
        except Exception:
            if os.environ.get("BEDROCK_DEBUG"):
                import traceback

                traceback.print_exc()
    from ..parsers.github_parser import GithubParser

    return GithubParser().parse(repos)