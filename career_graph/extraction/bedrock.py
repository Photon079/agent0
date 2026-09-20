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
        "DO NOT just list surface-level languages like Python or JavaScript. "
        "You MUST extract highly granular, in-depth technical skills: specific frameworks (e.g. React, Next.js, FastAPI, Spring Boot), "
        "databases (e.g. PostgreSQL, Redis, MongoDB), cloud services (e.g. AWS S3, EC2, ECS), ML models (e.g. BERT, LLaMA), and architectures. "
        "Dig deep into the technical stack. "
        "Also infer the candidate's 'location' (e.g. 'India', 'US', or specific city/country) and 'experience_level' (e.g. 'Junior', 'Mid-Level', 'Senior', 'Lead') based on their timeline. "
        'Return ONLY valid JSON with keys "name", "email" (string or null), "location" (string or null), "experience_level" (string or null), '
        '"skills" (array of {"name","confidence","evidence"}) and '
        '"projects" (array of {"name","description","url"}). Use exact skill '
        'names from the text.'
    )
    user = f"<resume>\n{text[:12000]}\n</resume>"
    raw = _converse(system, user, RESUME_MODEL)
    data = _require_json(_parse_json_text(raw))
    return {
        "name": str(data.get("name") or "Unknown"),
        "email": (data.get("email") or None),
        "location": (data.get("location") or None),
        "experience_level": (data.get("experience_level") or None),
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


# ---------------- Job Postings ----------------

def _bedrock_job_skills(description: str, title: str) -> Dict[str, Any]:
    system = (
        "You extract required technical skills from software job descriptions. "
        "DO NOT just list generic languages. You MUST extract granular frameworks (e.g. React, Spring Boot), "
        "libraries, databases, ML models, cloud architecture components, and specific tools required by the job. "
        "Also infer the strict 'location' requirement (e.g. 'Remote US', 'India', 'Global Remote', 'San Francisco') and 'experience_level' (e.g. 'Junior', 'Mid-Level', 'Senior', 'Lead'). "
        'Return ONLY valid JSON: {"skills":[{"name":"FastAPI","importance":1.0}], "location": "US Remote", "experience_level": "Senior"}. '
        "importance is the weight of the requirement (1.0 = required, "
        "0.5 = nice-to-have, 0.2 = rare mention). Deduplicate skills."
    )
    user = f"<job title=\"{title}\">\n{description[:12000]}\n</job>"
    raw = _converse(system, user, JD_MODEL)
    data = _require_json(_parse_json_text(raw))
    return {
        "skills": data.get("skills", []),
        "location": data.get("location") or None,
        "experience_level": data.get("experience_level") or None,
    }


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
    return {
        "skills": parsed.get("skills", []),
        "location": parsed.get("location") or None,
        "experience_level": parsed.get("experience_level") or None,
    }


# ---------------- GitHub repos ----------------

def _bedrock_github_repos(repos: List[Dict[str, Any]]) -> Dict[str, Any]:
    from ..parsers.github_parser import GithubParser

    base = GithubParser().parse(repos)
    with_readme = [r for r in repos if (r.get("readme_text") or "").strip()]
    if not with_readme:
        return base

    system = (
        "For each GitHub repository, infer the in-depth tech skills, libraries, frameworks, ML models, and infrastructure components "
        "shown in its README and dependency files. "
        "DO NOT just list basic languages. Extract highly granular, specific dependencies (e.g. 'PyTorch', 'TensorFlow', 'PostgreSQL', 'Redis', 'Docker', 'React', 'FastAPI') "
        "instead of just the language. Go as deep as possible into the tech stack. "
        'Return ONLY valid JSON: {"repos":{"repo_name":["FastAPI","Docker","Redis"]}}. '
        "Use exact, canonical skill names."
    )
    user_blocks = []
    for r in repos:
        readme = (r.get("readme_text") or "")[:4000]
        deps = r.get("dependency_files") or {}
        if not readme and not deps:
            continue
        deps_text = "\n".join(f"--- {name} ---\n{content}" for name, content in deps.items())
        user_blocks.append(f"<repo name={r.get('name')}>\n{readme}\n{deps_text}\n</repo>")
    
    if not user_blocks:
        return base

    user = "\n\n".join(user_blocks)
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


# ---------------- Gap Micro-Projects ----------------

def suggest_micro_project(job_skills: List[str], missing_skills: List[str], candidate_skills: List[str]) -> Dict[str, str]:
    """Suggest a small project to bridge the gap between candidate skills and job requirements."""
    if not USE_BEDROCK:
        skills_str = ", ".join(missing_skills[:3])
        return {
            "title": f"Bridge the Gap: {skills_str} Project",
            "description": (
                f"Build a small project to learn {skills_str}. Start by reading the official documentation and "
                f"following a tutorial on [freeCodeCamp](https://www.freecodecamp.org/news/search/?query={missing_skills[0]}). "
                f"**Step 1**: Set up a basic Hello World. "
                f"**Step 2**: Integrate {missing_skills[0]} with your existing knowledge of {candidate_skills[0] if candidate_skills else 'your preferred language'}. "
                f"**Step 3**: Deploy it and add it to your GitHub to prove your proficiency."
            )
        }
    
    system = (
        "You are a senior engineering manager. A candidate is applying for a job, but they are missing certain skills. "
        "Suggest a highly specific, actionable 'micro-project' they can build over a weekend to learn the missing skills "
        "and prove they can do the job. The project should ideally combine their existing skills with the missing ones. "
        "Provide a detailed step-by-step guide on how to build it. "
        "CRITICAL: You MUST include markdown links to good learning resources (e.g., official docs, freeCodeCamp, or specific tutorials) for the missing skills. "
        'Return ONLY valid JSON: {"title": "Project Name", "description": "Detailed description with steps and markdown links to resources"}'
    )
    user = (
        f"Job requires: {', '.join(job_skills)}\n"
        f"Candidate has: {', '.join(candidate_skills)}\n"
        f"Candidate is MISSING: {', '.join(missing_skills)}\n"
    )
    try:
        raw = _converse(system, user, JD_MODEL)
        return _require_json(_parse_json_text(raw))
    except Exception:
        skills_str = ", ".join(missing_skills[:3])
        return {
            "title": f"Bridge the Gap: {skills_str} Project",
            "description": (
                f"Build a small project to learn {skills_str}. Start by reading the official documentation and "
                f"following a tutorial on [freeCodeCamp](https://www.freecodecamp.org/news/search/?query={missing_skills[0]}). "
                f"**Step 1**: Set up a basic Hello World. "
                f"**Step 2**: Integrate {missing_skills[0]} with your existing knowledge of {candidate_skills[0] if candidate_skills else 'your preferred language'}. "
                f"**Step 3**: Deploy it and add it to your GitHub to prove your proficiency."
            )
        }


# ---------------- Proof-Backed Bullets ----------------

def generate_proof_bullets(job_title: str, evidence: List[Dict]) -> List[Dict]:
    """Generate resume bullets for a job tied directly to graph evidence."""
    if not USE_BEDROCK:
        return [
            {
                "bullet": f"Leveraged {e.get('skill')} effectively.",
                "evidence_ids": [p.get("name") for p in e.get("project_evidence", [])][:1],
                "skill": e.get("skill")
            }
            for e in evidence[:3]
        ]

    system = (
        "You are an expert resume writer. Given a job title and a candidate's verifiable evidence (projects, experience) "
        "for their skills, generate 3-5 highly impactful, quantifiable resume bullets. "
        "Crucially, for EACH bullet, you MUST provide the exact names of the projects or experiences you used as proof from the evidence provided. "
        'Return ONLY valid JSON: {"bullets": [{"bullet": "Designed...", "evidence_ids": ["ProjectA", "CompanyB"], "skill": "Python"}]}'
    )
    user_blocks = [f"Job Title: {job_title}\n\nEvidence:"]
    for e in evidence:
        user_blocks.append(f"Skill: {e['skill']}")
        for p in e.get("project_evidence", []):
            user_blocks.append(f"  Project: {p['name']} ({p.get('commits', 0)} commits) - {p.get('description', '')}")
        for exp in e.get("experience_evidence", []):
            user_blocks.append(f"  Experience: {exp['role']} @ {exp['company']} ({exp.get('duration', '')})")

    try:
        raw = _converse(system, "\n".join(user_blocks), RESUME_MODEL)
        data = _require_json(_parse_json_text(raw))
        return data.get("bullets", [])
    except Exception:
        return []