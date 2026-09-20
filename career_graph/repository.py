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


# Experience level tier mapping for numeric comparison
_EXP_TIERS = {
    "intern": 0, "internship": 0,
    "entry": 1, "entry-level": 1, "entry level": 1, "junior": 1, "jr": 1,
    "associate": 1, "graduate": 1,
    "mid": 2, "mid-level": 2, "mid level": 2, "intermediate": 2,
    "senior": 3, "sr": 3,
    "staff": 4, "lead": 4, "principal": 4,
    "manager": 5, "director": 5, "vp": 6, "head": 5,
}


def _exp_tier(label: str) -> int:
    """Map an experience label string to a numeric tier (0=intern … 6=VP)."""
    label = (label or "").lower().strip()
    # Try exact match first
    if label in _EXP_TIERS:
        return _EXP_TIERS[label]
    # Scan for keyword tokens
    for token, tier in _EXP_TIERS.items():
        if token in label:
            return tier
    return -1  # unknown


def match_jobs_by_skill_overlap(candidate_id: int, limit: int = 10):
    """Return ranked job matches for a candidate.

    Improvements over the naive version:
    - Requires genuine skill overlap (≥1 match AND ≥20% of job requirements).
    - Uses tier-based experience comparison instead of string equality:
        * same tier        → no penalty
        * 1 tier away      → small penalty (-1)
        * 2 tiers away     → medium penalty (-2)
        * ≥3 tiers away    → large penalty (-4, job unlikely suitable)
    - Returns a match_pct alongside overlap so the frontend can display it.
    """
    from .models import job_requirement, Skill, JobPosting
    from .db import get_session

    with get_session() as session:
        cand = session.get(Candidate, candidate_id)
        if not cand:
            return []
        cand_skill_ids = [s.id for s in cand.skills]
        if not cand_skill_ids:
            return []

        # --- Step 1: count how many of the candidate's skills each job requires ---
        stmt = (
            select(JobPosting, func.count(Skill.id).label("overlap"))
            .join(job_requirement, JobPosting.id == job_requirement.c.job_id)
            .join(Skill, Skill.id == job_requirement.c.skill_id)
            .where(Skill.id.in_(cand_skill_ids))
            .group_by(JobPosting.id)
            .order_by(func.count(Skill.id).desc())
            .limit(limit * 8)  # wider net; we'll filter below
        )
        rows = session.execute(stmt).all()

        # Pre-fetch total requirement counts for all matched job ids in one query
        job_ids = [row[0].id for row in rows]
        req_counts_stmt = (
            select(job_requirement.c.job_id, func.count().label("total"))
            .where(job_requirement.c.job_id.in_(job_ids))
            .group_by(job_requirement.c.job_id)
        )
        req_counts = {r[0]: r[1] for r in session.execute(req_counts_stmt).all()}

        cand_loc = (cand.location or "").lower()
        # Default unknown candidate experience to Entry/Junior (tier 1).
        # A candidate who listed no work history should not score as a perfect
        # experience match against Senior or Lead roles.
        raw_tier = _exp_tier(cand.experience_level or "")
        cand_exp_tier = raw_tier if raw_tier >= 0 else 1  # Entry by default

        scored_jobs = []
        for job, overlap in rows:
            total_req = req_counts.get(job.id, 1)
            match_pct = round(overlap / total_req * 100) if total_req else 0

            # --- Relevance filter: skip jobs with trivially low overlap ---
            # Must match at least 1 skill AND at least 20% of requirements
            if overlap < 1 or match_pct < 20:
                continue

            score = float(overlap)
            penalty_reasons = []

            # --- Experience level penalty (tier-based) ---
            # If job has no stored experience_level, infer tier from the title
            job_exp_source = job.experience_level or job.title or ""
            job_exp_tier = _exp_tier(job_exp_source)
            if cand_exp_tier >= 0 and job_exp_tier >= 0:
                tier_diff = cand_exp_tier - job_exp_tier
                if tier_diff < 0: # Candidate is less experienced than job requires
                    diff = abs(tier_diff)
                    if diff == 1:
                        score *= 0.7
                        penalty_reasons.append(f"Stretch role ({job.experience_level})")
                    elif diff == 2:
                        score *= 0.3
                        penalty_reasons.append(f"Major stretch ({job.experience_level})")
                    elif diff >= 3:
                        score *= 0.1
                        penalty_reasons.append(f"Unlikely match ({job.experience_level})")
                elif tier_diff > 0: # Candidate is MORE experienced than job requires
                    if tier_diff == 1:
                        score *= 0.9 # Slight penalty for being overqualified
                    elif tier_diff >= 2:
                        score *= 0.6
                        penalty_reasons.append(f"Overqualified ({job.experience_level})")
            elif job.experience_level and not cand_exp_tier >= 0:
                # Job has a level but candidate level is unknown — mild penalty
                score *= 0.9

            # --- Location penalty ---
            if cand_loc and job.location:
                j_loc = job.location.lower()
                is_global = "global" in j_loc or j_loc in ("remote", "worldwide", "anywhere")
                if not is_global and cand_loc not in j_loc and j_loc not in cand_loc:
                    score *= 0.5
                    penalty_reasons.append(f"Located in {job.location}")

            scored_jobs.append((job, score, penalty_reasons, overlap, match_pct))

        # Sort by penalized score descending
        scored_jobs.sort(key=lambda x: x[1], reverse=True)

        # Return as (job, overlap, penalty_reasons) — same shape as before
        # but now overlap is still raw skill count; score is internal
        return [(job, overlap, reasons) for job, _score, reasons, overlap, _pct in scored_jobs[:limit]]


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