"""Resume Tailoring Agent — Phase 3 of the Resume Tailoring Pipeline.

Uses Amazon Bedrock (Claude Sonnet) to generate a structured, job-tailored
resume JSON from the ResumeContext.  Falls back to a deterministic template
when Bedrock is unavailable.

STRICT GROUNDING RULES are enforced via the system prompt — the agent may
only rewrite/reorder existing facts, never invent new ones.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Model for resume tailoring — Sonnet for better constraint following (PRD L4)
TAILOR_MODEL = os.environ.get(
    "BEDROCK_RESUME_TAILOR_MODEL",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
)
USE_BEDROCK = os.environ.get("CAREER_GRAPH_USE_BEDROCK", "").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# System prompt — strict grounding rules
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a Grounded Resume Tailoring Agent.

Your task is to tailor a candidate's resume for a specific job.

The candidate's knowledge graph is the source of truth.

STRICT GROUNDING RULES:

1. Use ONLY facts present in the supplied candidate data and graph evidence.

2. NEVER invent:
   - technologies
   - programming languages
   - frameworks
   - projects
   - companies
   - job titles
   - responsibilities
   - achievements
   - metrics
   - certifications
   - education
   - employment experience

3. You may rewrite existing facts for clarity and relevance.

4. You may reorder existing projects based on job relevance.

5. You may prioritize skills that are explicitly required by the job.

6. You may shorten or remove irrelevant content.

7. You may combine facts only when the combination is explicitly supported by the evidence.

8. If a job requires a skill that the candidate does not have evidence for, classify it as a skill gap.

9. NEVER convert a skill gap into claimed candidate experience.

10. Every generated project or experience bullet must contain one or more evidence_ids from the supplied evidence.

11. Every evidence_id must correspond to an evidence item supplied in the input context.

12. Do not create fake metrics.

13. Do not exaggerate candidate experience.

14. Preserve factual accuracy over keyword optimization.

15. Return ONLY valid JSON matching the schema below. No prose, no markdown.

REQUIRED JSON SCHEMA:

{
  "candidate": {
    "name": "string",
    "email": "string or empty",
    "phone": "string or empty",
    "linkedin": "string or empty",
    "github": "string or empty"
  },
  "summary": {
    "text": "A 2-3 sentence professional summary highlighting relevant skills",
    "evidence_ids": ["list of evidence_ids used"]
  },
  "skills": {
    "languages": ["list of programming languages from candidate data"],
    "frameworks": ["list of frameworks from candidate data"],
    "ai_ml": ["list of AI/ML tools from candidate data"],
    "cloud": ["list of cloud services from candidate data"],
    "databases": ["list of databases from candidate data"],
    "tools": ["list of other tools from candidate data"]
  },
  "experience": [
    {
      "experience_id": "string",
      "company": "string",
      "role": "string",
      "dates": "string",
      "bullets": [
        {
          "text": "achievement/responsibility bullet",
          "evidence_ids": ["list of evidence_ids"]
        }
      ]
    }
  ],
  "projects": [
    {
      "project_id": "string",
      "name": "string",
      "technologies": ["list of technologies from evidence"],
      "bullets": [
        {
          "text": "project description bullet",
          "evidence_ids": ["list of evidence_ids"]
        }
      ]
    }
  ],
  "education": [],
  "achievements": [],
  "skill_gaps": ["list of job-required skills the candidate lacks"]
}

The goal is to present the candidate's REAL experience in the most relevant way for the target job.
"""


# ---------------------------------------------------------------------------
# Bedrock-based tailoring
# ---------------------------------------------------------------------------

def _build_user_prompt(context: Dict[str, Any]) -> str:
    """Build the user message from ResumeContext."""
    sections = []

    # Job information
    job = context.get("job", {})
    sections.append("=== TARGET JOB ===")
    sections.append(f"Title: {job.get('title', '')}")
    sections.append(f"Company: {job.get('company', '')}")
    sections.append(f"Location: {job.get('location', '')}")
    sections.append(f"Experience Level: {job.get('experience_level', '')}")
    sections.append(f"Required Skills: {', '.join(job.get('required_skills', []))}")
    if job.get("description"):
        sections.append(f"Description:\n{job['description'][:2000]}")

    # Candidate information
    cand = context.get("candidate", {})
    sections.append("\n=== CANDIDATE ===")
    sections.append(f"Name: {cand.get('name', '')}")
    sections.append(f"Email: {cand.get('email', '')}")
    sections.append(f"Location: {cand.get('location', '')}")
    sections.append(f"Experience Level: {cand.get('experience_level', '')}")
    sections.append(f"GitHub: {cand.get('github', '')}")

    # Skills match
    sections.append(f"\n=== MATCHED SKILLS ===")
    sections.append(", ".join(context.get("matched_skills", [])))
    sections.append(f"\n=== MISSING SKILLS (GAPS) ===")
    sections.append(", ".join(context.get("missing_skills", [])))
    sections.append(f"\n=== ALL CANDIDATE SKILLS ===")
    sections.append(", ".join(context.get("all_candidate_skills", [])))

    # Evidence
    sections.append("\n=== GRAPH EVIDENCE ===")
    for ev in context.get("evidence", []):
        ev_line = f"[{ev['evidence_id']}] Skill={ev['skill']}, Type={ev['evidence_type']}"
        if ev.get("project_name"):
            ev_line += f", Project={ev['project_name']}"
        if ev.get("source_url"):
            ev_line += f", URL={ev['source_url']}"
        if ev.get("description"):
            ev_line += f", Desc={ev['description'][:200]}"
        if ev.get("company"):
            ev_line += f", Company={ev['company']}"
        if ev.get("role"):
            ev_line += f", Role={ev['role']}"
        sections.append(ev_line)

    # Projects
    sections.append("\n=== CANDIDATE PROJECTS ===")
    for proj in context.get("relevant_projects", []):
        p_line = f"Project: {proj.get('name', '')}"
        if proj.get("description"):
            p_line += f" — {proj['description'][:200]}"
        if proj.get("url"):
            p_line += f" ({proj['url']})"
        if proj.get("skills"):
            p_line += f" [Skills: {', '.join(proj['skills'])}]"
        if proj.get("commit_count", 0) > 0:
            p_line += f" [{proj['commit_count']} commits]"
        sections.append(p_line)

    # Experience
    sections.append("\n=== CANDIDATE EXPERIENCE ===")
    for exp in context.get("relevant_experience", []):
        e_line = f"{exp.get('title', '')} at {exp.get('company', '')}"
        e_line += f" ({exp.get('start_date', '')} - {exp.get('end_date', '')})"
        if exp.get("description"):
            e_line += f"\n  {exp['description'][:300]}"
        sections.append(e_line)

    return "\n".join(sections)


def _tailor_via_bedrock(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate tailored resume JSON via Amazon Bedrock."""
    from career_graph.extraction.bedrock import _converse, _parse_json_text

    user_prompt = _build_user_prompt(context)
    log.info("[AGENT] Sending context to Bedrock (%s), prompt length=%d chars",
             TAILOR_MODEL, len(user_prompt))

    raw = _converse(SYSTEM_PROMPT, user_prompt, TAILOR_MODEL, max_tokens=4096)
    resume_json = _parse_json_text(raw)

    if not isinstance(resume_json, dict):
        raise ValueError("Bedrock returned non-dict JSON")

    log.info("[AGENT] Bedrock returned resume JSON with %d projects, %d experience entries",
             len(resume_json.get("projects", [])), len(resume_json.get("experience", [])))
    return resume_json


def _tailor_via_bedrock_with_violations(
    context: Dict[str, Any],
    violations: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Regenerate after grounding violations — sends violations as feedback."""
    from career_graph.extraction.bedrock import _converse, _parse_json_text

    user_prompt = _build_user_prompt(context)
    user_prompt += "\n\n=== GROUNDING VIOLATIONS FROM PREVIOUS ATTEMPT ==="
    user_prompt += "\nThe following claims were NOT supported by evidence. Remove or fix them:\n"
    for v in violations:
        user_prompt += f"- Claim: \"{v.get('claim', '')}\" — Reason: {v.get('reason', '')}\n"
    user_prompt += "\nGenerate a corrected resume JSON that does NOT contain any of the above violations."

    raw = _converse(SYSTEM_PROMPT, user_prompt, TAILOR_MODEL, max_tokens=4096)
    return _parse_json_text(raw)


# ---------------------------------------------------------------------------
# Deterministic fallback (no LLM needed)
# ---------------------------------------------------------------------------

_SKILL_CATEGORIES = {
    "languages": {"python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
                  "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "shell", "bash",
                  "perl", "lua", "dart", "elixir", "haskell", "c"},
    "frameworks": {"react", "angular", "vue", "next.js", "fastapi", "django", "flask",
                   "spring", "express", "rails", "laravel", ".net", "svelte", "gatsby",
                   "nuxt", "nest.js", "streamlit", "gradio", "spring boot"},
    "ai_ml": {"tensorflow", "pytorch", "scikit-learn", "keras", "hugging face",
              "langchain", "openai", "bedrock", "sagemaker", "bert", "llama",
              "gpt", "xgboost", "pandas", "numpy", "scipy", "matplotlib",
              "machine learning", "deep learning", "nlp", "computer vision",
              "ml", "ai"},
    "cloud": {"aws", "azure", "gcp", "lambda", "ec2", "s3", "ecs", "fargate",
              "cloudformation", "terraform", "docker", "kubernetes", "amplify",
              "api gateway", "cloudwatch", "step functions", "sqs", "sns",
              "dynamodb"},
    "databases": {"postgresql", "mysql", "mongodb", "redis", "elasticsearch",
                  "sqlite", "cassandra", "neo4j", "falkordb", "mariadb",
                  "sql", "nosql", "supabase", "firebase"},
    "tools": {"git", "github", "gitlab", "jira", "ci/cd", "jenkins", "github actions",
              "linux", "nginx", "graphql", "rest", "grpc", "kafka", "rabbitmq",
              "prometheus", "grafana", "datadog"},
}


def _categorize_skill(skill_name: str) -> str:
    """Determine which category a skill belongs to."""
    lower = skill_name.lower()
    for category, keywords in _SKILL_CATEGORIES.items():
        if lower in keywords or any(kw in lower for kw in keywords):
            return category
    return "tools"


def _tailor_deterministic(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build resume JSON deterministically from context — no LLM, no hallucination risk."""
    log.info("[AGENT] Using deterministic fallback (Bedrock disabled)")

    cand = context.get("candidate", {})
    job = context.get("job", {})
    evidence = context.get("evidence", [])
    matched_skills = context.get("matched_skills", [])
    missing_skills = context.get("missing_skills", [])
    all_skills = context.get("all_candidate_skills", [])
    projects = context.get("relevant_projects", []) or context.get("projects", [])
    experiences = context.get("relevant_experience", []) or context.get("experiences", [])


    # Build evidence ID lookup
    ev_by_project: Dict[str, List[str]] = {}
    ev_by_skill: Dict[str, List[str]] = {}
    all_ev_ids = []
    for ev in evidence:
        eid = ev.get("evidence_id", "")
        all_ev_ids.append(eid)
        if ev.get("project_name"):
            ev_by_project.setdefault(ev["project_name"], []).append(eid)
        ev_by_skill.setdefault(ev.get("skill", ""), []).append(eid)

    # Categorize skills
    skills_out: Dict[str, List[str]] = {
        "languages": [], "frameworks": [], "ai_ml": [],
        "cloud": [], "databases": [], "tools": [],
    }
    for s in all_skills:
        cat = _categorize_skill(s)
        if s not in skills_out[cat]:
            skills_out[cat].append(s)

    # Summary
    top_matched = matched_skills[:5]
    summary_text = f"{cand.get('name', 'Candidate')}"
    if cand.get("experience_level"):
        summary_text += f", {cand['experience_level']}"
    summary_text += " software engineer"
    if top_matched:
        summary_text += f" with experience in {', '.join(top_matched[:3])}"
    summary_text += f". Seeking {job.get('title', 'a role')} at {job.get('company', 'target company')}."

    # Experience entries
    experience_out = []
    for exp in experiences:
        exp_ev_ids = []
        for s in matched_skills:
            if s.lower() in (exp.get("description") or "").lower():
                exp_ev_ids.extend(ev_by_skill.get(s, []))

        bullets = []
        if exp.get("description"):
            bullets.append({
                "text": exp["description"][:200],
                "evidence_ids": list(set(exp_ev_ids))[:3],
            })

        experience_out.append({
            "experience_id": str(exp.get("id", "")),
            "company": exp.get("company", ""),
            "role": exp.get("title", ""),
            "dates": f"{exp.get('start_date', '')} - {exp.get('end_date', '')}",
            "bullets": bullets,
        })

    # Project entries — order by relevance (number of matched skills)
    projects_scored = []
    for proj in projects:
        proj_skills = [s.lower() for s in proj.get("skills", [])]
        relevance = sum(1 for s in matched_skills if s.lower() in proj_skills)
        projects_scored.append((relevance, proj))
    projects_scored.sort(key=lambda x: x[0], reverse=True)

    projects_out = []
    for _score, proj in projects_scored:
        proj_name = proj.get("name", "")
        p_ev_ids = ev_by_project.get(proj_name, [])

        bullets = []
        if proj.get("description"):
            bullets.append({
                "text": proj["description"][:200],
                "evidence_ids": p_ev_ids[:3],
            })

        # Add a tech stack bullet
        if proj.get("skills"):
            bullets.append({
                "text": f"Built with {', '.join(proj['skills'][:6])}",
                "evidence_ids": p_ev_ids[:2],
            })

        projects_out.append({
            "project_id": str(proj.get("id", "")),
            "name": proj_name,
            "technologies": proj.get("skills", []),
            "bullets": bullets,
        })

    return {
        "candidate": {
            "name": cand.get("name", ""),
            "email": cand.get("email", ""),
            "phone": cand.get("phone", ""),
            "linkedin": cand.get("linkedin", ""),
            "github": cand.get("github", ""),
        },
        "summary": {
            "text": summary_text,
            "evidence_ids": all_ev_ids[:5],
        },
        "skills": skills_out,
        "experience": experience_out,
        "projects": projects_out,
        "education": [],
        "achievements": [],
        "skill_gaps": missing_skills,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_tailored_resume(
    context: Dict[str, Any],
    violations: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Generate a tailored resume JSON from ResumeContext.

    Uses Bedrock when enabled, otherwise falls back to deterministic generation.

    Args:
        context: ResumeContext dict from resume_context.build_resume_context().
        violations: Optional list of grounding violations from a previous attempt
                    (used for regeneration loop).

    Returns:
        Structured resume JSON matching the schema.
    """
    log.info("[AGENT] Resume tailoring started")

    if USE_BEDROCK:
        try:
            if violations:
                resume_json = _tailor_via_bedrock_with_violations(context, violations)
            else:
                resume_json = _tailor_via_bedrock(context)
            log.info("[AGENT] Resume JSON generated via Bedrock")
            return resume_json
        except Exception as e:
            log.warning("[AGENT] Bedrock tailoring failed (%s); using deterministic fallback", e)
            if os.environ.get("BEDROCK_DEBUG"):
                import traceback
                traceback.print_exc()

    # Deterministic fallback — safe, no hallucination risk
    resume_json = _tailor_deterministic(context)
    log.info("[AGENT] Resume JSON generated via deterministic fallback")
    return resume_json


class ResumeTailoringAgent:
    """Agent class for generating tailored resume JSON."""

    def generate_tailored_resume(self, context: Dict[str, Any], violations: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Generate structured resume JSON."""
        return generate_tailored_resume(context, violations)

    def _generate_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Direct access to deterministic generator for testing."""
        return _tailor_deterministic(context)

