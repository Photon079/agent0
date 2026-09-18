from sqlalchemy import select, func
from .models import Candidate, Skill, Project, JobPosting
from .db import get_session


def create_candidate(name: str, email: str | None = None):
    with get_session() as session:
        candidate = Candidate(name=name, email=email)
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        return candidate


def get_candidate(candidate_id: int):
    with get_session() as session:
        return session.get(Candidate, candidate_id)


def create_skill(canonical_name: str, aliases: list | None = None, category: str | None = None):
    with get_session() as session:
        skill = Skill(canonical_name=canonical_name, aliases=aliases or [], category=category)
        session.add(skill)
        session.commit()
        session.refresh(skill)
        return skill


def link_candidate_skill(candidate_id: int, skill_id: int, confidence: float = 0.0, evidence: dict | None = None):
    from .models import candidate_skill

    with get_session() as session:
        # ensure we don't duplicate the association (unique constraint)
        exists_stmt = select(candidate_skill).where(
            candidate_skill.c.candidate_id == candidate_id,
            candidate_skill.c.skill_id == skill_id,
        )
        res = session.execute(exists_stmt).first()
        if res:
            return

        # insert association row with properties
        session.execute(
            candidate_skill.insert().values(candidate_id=candidate_id, skill_id=skill_id, confidence=confidence, evidence=evidence)
        )
        session.commit()


def match_jobs_by_skill_overlap(candidate_id: int, limit: int = 10):
    # naive implementation: count overlapping skills
    from .models import job_requirement, candidate_skill, Skill, JobPosting
    from .db import get_session

    with get_session() as session:
        # get candidate skill ids
        cand = session.get(Candidate, candidate_id)
        if not cand:
            return []
        cand_skill_ids = [s.id for s in cand.skills]
        if not cand_skill_ids:
            return []

        stmt = (
            select(JobPosting, func.count(Skill.id).label("overlap"))
            .join(job_requirement, JobPosting.id == job_requirement.c.job_id)
            .join(Skill, Skill.id == job_requirement.c.skill_id)
            .where(Skill.id.in_(cand_skill_ids))
            .group_by(JobPosting.id)
            .order_by(func.count(Skill.id).desc())
            .limit(limit)
        )
        rows = session.execute(stmt).all()
        return [(row[0], row[1]) for row in rows]


def gap_detection(candidate_id: int, job_id: int):
    """Return list of skill canonical names required by the job but missing from the candidate."""
    from .models import job_requirement, Skill

    with get_session() as session:
        cand = session.get(Candidate, candidate_id)
        if not cand:
            return []
        cand_skill_ids = {s.id for s in cand.skills}

        # required skill ids for job
        stmt = (
            select(Skill)
            .join(job_requirement, Skill.id == job_requirement.c.skill_id)
            .where(job_requirement.c.job_id == job_id)
        )
        req_skills = [r for r in session.scalars(stmt).all()]
        missing = [s.canonical_name for s in req_skills if s.id not in cand_skill_ids]
        return missing


def evidence_for_skill(skill_id: int):
    """Return evidence objects (projects, candidates) that support this skill.

    Format:
      {"projects": [{"id":..., "name":..., "evidence":...}, ...], "candidates": [...]}
    """
    from .models import project_skill, candidate_skill, Project, Candidate

    with get_session() as session:
        projects = (
            session.execute(
                select(Project, project_skill.c.evidence)
                .join(project_skill, Project.id == project_skill.c.project_id)
                .where(project_skill.c.skill_id == skill_id)
            )
            .all()
        )

        candidates = (
            session.execute(
                select(Candidate, candidate_skill.c.evidence)
                .join(candidate_skill, Candidate.id == candidate_skill.c.candidate_id)
                .where(candidate_skill.c.skill_id == skill_id)
            )
            .all()
        )

        return {
            "projects": [{"id": p[0].id, "name": p[0].name, "evidence": p[1]} for p in projects],
            "candidates": [{"id": c[0].id, "name": c[0].name, "evidence": c[1]} for c in candidates],
        }