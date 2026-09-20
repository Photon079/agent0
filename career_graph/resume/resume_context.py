"""ResumeContext Builder — Phase 2 of the Resume Tailoring Pipeline.

Assembles a normalized ResumeContext dict containing only information relevant
to the target job.  This is the single object sent to the Resume Tailoring
Agent — it must be clean, minimal, and complete.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select as sa_select
from sqlalchemy.orm import selectinload

from career_graph.backend import get_active_backend
from career_graph.db import get_session
from career_graph.models import (
    Candidate,
    Experience,
    JobPosting,
    Project,
    Skill,
    candidate_skill,
    job_requirement,
    project_skill,
)
from career_graph.resume.evidence_retrieval import (
    EvidenceItem,
    evidence_by_skill,
    retrieve_evidence,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate_dict(cand: Candidate, github_url: Optional[str] = None) -> Dict[str, Any]:
    """Serialize a Candidate ORM object to a plain dict."""
    return {
        "id": cand.id,
        "name": cand.name or "",
        "email": cand.email or "",
        "phone": "",  # Not in current schema
        "location": cand.location or "",
        "experience_level": cand.experience_level or "",
        "linkedin": "",  # Not in current schema
        "github": github_url or "",
    }


def _job_dict(job: JobPosting, required_skills: List[str]) -> Dict[str, Any]:
    """Serialize a JobPosting ORM object to a plain dict."""
    return {
        "id": job.id,
        "title": job.title or "",
        "company": job.company or "",
        "description": (job.description or "")[:3000],  # Limit context size
        "url": job.url or "",
        "location": job.location or "",
        "experience_level": job.experience_level or "",
        "required_skills": required_skills,
    }


def _project_dict(proj: Project) -> Dict[str, Any]:
    """Serialize a Project ORM object to a plain dict."""
    return {
        "id": proj.id,
        "name": proj.name or "",
        "description": proj.description or "",
        "url": proj.url or "",
        "commit_count": proj.commit_count or 0,
        "source": proj.source or "",
    }


def _experience_dict(exp: Experience) -> Dict[str, Any]:
    """Serialize an Experience ORM object to a plain dict."""
    return {
        "id": exp.id,
        "title": exp.title or "",
        "company": exp.company or "",
        "start_date": str(exp.start_date or ""),
        "end_date": str(exp.end_date or ""),
        "description": exp.description or "",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_resume_context(candidate_id, job_id) -> Dict[str, Any]:
    """Build a normalized ResumeContext for the Resume Tailoring Agent.

    Steps:
      1. Load candidate and job from the relational store.
      2. Compute matched and missing skills.
      3. Retrieve graph evidence for matched skills.
      4. Collect relevant projects and experiences.
      5. Return a clean, minimal context dict.

    Args:
        candidate_id: Candidate identifier (int or str).
        job_id: Job posting identifier (int or str).

    Returns:
        Dict with keys: candidate, job, matched_skills, missing_skills,
        evidence, evidence_by_skill, relevant_projects, relevant_experience.

    Raises:
        ValueError: if candidate or job not found.
    """
    # Normalize IDs
    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
    except ValueError:
        raise ValueError(f"Invalid candidate_id: {candidate_id}")

    try:
        job_id_int = int(str(job_id).replace("job:", ""))
    except ValueError:
        raise ValueError(f"Invalid job_id: {job_id}")

    log.info("[CONTEXT] Building ResumeContext for candidate=%s, job=%s", cand_id_int, job_id_int)

    with get_session() as session:
        # --- 1. Load candidate ---
        cand = session.scalar(
            sa_select(Candidate)
            .where(Candidate.id == cand_id_int)
            .options(selectinload(Candidate.skills), selectinload(Candidate.projects))
        )
        if not cand:
            raise ValueError(f"Candidate {cand_id_int} not found")

        cand_skill_names = [s.canonical_name for s in cand.skills]
        cand_skill_names_lower = {s.lower() for s in cand_skill_names}

        # --- 2. Load job ---
        job = session.scalar(
            sa_select(JobPosting)
            .where(JobPosting.id == job_id_int)
            .options(selectinload(JobPosting.skills))
        )
        if not job:
            raise ValueError(f"Job posting {job_id_int} not found")

        job_skill_names = [s.canonical_name for s in job.skills]

        # --- 3. Compute matched / missing skills ---
        matched_skills = [s for s in job_skill_names if s.lower() in cand_skill_names_lower]
        missing_skills = [s for s in job_skill_names if s.lower() not in cand_skill_names_lower]

        log.info("[MATCH] %d matched, %d missing skills", len(matched_skills), len(missing_skills))

        # --- 4. Infer github URL from projects ---
        github_url = ""
        for proj in cand.projects:
            if proj.url and "github.com" in (proj.url or ""):
                # Extract the user's GitHub profile from a repo URL
                parts = proj.url.split("github.com/")
                if len(parts) > 1:
                    username = parts[1].split("/")[0]
                    github_url = f"https://github.com/{username}"
                    break

        # --- 5. Get relevant projects (projects that use any matched skill) ---
        matched_lower = {s.lower() for s in matched_skills}
        relevant_projects = []
        all_projects = []

        # Load projects with their skills
        for proj in cand.projects:
            # Eagerly load project skills within session scope
            proj_skills_q = (
                sa_select(Skill.canonical_name)
                .join(project_skill, Skill.id == project_skill.c.skill_id)
                .where(project_skill.c.project_id == proj.id)
            )
            proj_skill_names = [r[0] for r in session.execute(proj_skills_q).all()]

            pdict = _project_dict(proj)
            pdict["skills"] = proj_skill_names
            all_projects.append(pdict)

            # Check if project uses any matched skill
            if any(s.lower() in matched_lower for s in proj_skill_names):
                relevant_projects.append(pdict)

        # --- 6. Get relevant experiences ---
        exps = session.scalars(
            sa_select(Experience).where(Experience.candidate_id == cand_id_int)
        ).all()
        all_experiences = [_experience_dict(e) for e in exps]

        # Filter to relevant experiences (mention any matched skill in description)
        relevant_experience = []
        for exp_dict in all_experiences:
            desc_lower = exp_dict.get("description", "").lower()
            if any(s.lower() in desc_lower for s in matched_skills):
                relevant_experience.append(exp_dict)

        # Include all experiences if none are specifically relevant
        # (better to show all work history than none)
        if not relevant_experience and all_experiences:
            relevant_experience = all_experiences

        # --- Serialize candidate/job (must be inside session scope) ---
        cand_dict = _candidate_dict(cand, github_url)
        job_dict_out = _job_dict(job, job_skill_names)

    # --- 7. Retrieve graph evidence (outside session — has its own) ---
    evidence_items = retrieve_evidence(candidate_id, matched_skills)
    evidence_dicts = [e.to_dict() for e in evidence_items]
    evidence_grouped = evidence_by_skill(evidence_items)

    log.info("[CONTEXT] ResumeContext ready: %d evidence items, %d projects, %d experiences",
             len(evidence_dicts), len(relevant_projects), len(relevant_experience))

    return {
        "candidate": cand_dict,
        "job": job_dict_out,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "evidence": evidence_dicts,
        "evidence_by_skill": evidence_grouped,
        "relevant_projects": relevant_projects,
        "all_projects": all_projects,
        "relevant_experience": relevant_experience,
        "all_candidate_skills": cand_skill_names,
    }


class ResumeContextBuilder:
    """Builder class for assembling normalized ResumeContext dicts."""

    def build_context(
        self,
        candidate_data: Dict[str, Any],
        job_description: Dict[str, Any],
        matching_results: Optional[Dict[str, Any]] = None,
        evidence_report: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build context from dicts (or query database if IDs provided)."""
        if "id" in candidate_data and "id" in job_description and isinstance(candidate_data.get("id"), int) and isinstance(job_description.get("id"), int):
            try:
                return build_resume_context(candidate_data["id"], job_description["id"])
            except Exception as e:
                log.info(f"Direct DB lookup skipped ({e}), assembling from provided dicts.")

        cand_skills = candidate_data.get("skills", [])
        jd_skills = job_description.get("required_skills", [])

        cand_skills_lower = {s.lower() if isinstance(s, str) else s.get("name", "").lower() for s in cand_skills}
        matched = []
        missing = []
        for s in jd_skills:
            s_name = s if isinstance(s, str) else s.get("name", "")
            if s_name.lower() in cand_skills_lower:
                matched.append(s_name)
            else:
                missing.append(s_name)

        return {
            "candidate": {
                "name": candidate_data.get("name", "Candidate"),
                "email": candidate_data.get("email", ""),
                "location": candidate_data.get("location", ""),
                "experience_level": candidate_data.get("experience_level", ""),
            },
            "target_job": {
                "title": job_description.get("title", ""),
                "company": job_description.get("company", ""),
                "description": job_description.get("description", ""),
                "required_skills": jd_skills,
            },
            "skills": {
                "candidate_skills": cand_skills,
                "matched_skills": matched,
                "missing_skills": missing,
            },
            "experiences": candidate_data.get("experiences", []),
            "projects": candidate_data.get("projects", []),
            "matched_evidence": evidence_report or {},
        }

