"""Evidence Retrieval Service — Phase 1 of the Resume Tailoring Pipeline.

For every matched skill, retrieves supporting evidence from the candidate's
knowledge graph (projects, experiences) via the existing FalkorDB/SQLite
dual-backend infrastructure.

Each evidence item gets a stable, deterministic evidence_id so that downstream
resume bullets can be traced back to their source.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

from career_graph.backend import get_active_backend
from career_graph.db import get_session
from career_graph.models import (
    Candidate,
    Experience,
    Project,
    Skill,
    candidate_skill,
    project_skill,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evidence data structure
# ---------------------------------------------------------------------------

class EvidenceItem:
    """Single piece of evidence linking a skill to a project or experience."""

    __slots__ = (
        "evidence_id",
        "skill",
        "project_id",
        "project_name",
        "source_type",
        "source_url",
        "description",
        "confidence",
        "evidence_type",  # "project" or "experience"
        "company",
        "role",
        "duration",
    )

    def __init__(
        self,
        evidence_id: str,
        skill: str,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
        source_type: str = "github",
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        confidence: float = 0.8,
        evidence_type: str = "project",
        company: Optional[str] = None,
        role: Optional[str] = None,
        duration: Optional[str] = None,
    ):
        self.evidence_id = evidence_id
        self.skill = skill
        self.project_id = project_id
        self.project_name = project_name
        self.source_type = source_type
        self.source_url = source_url
        self.description = description
        self.confidence = confidence
        self.evidence_type = evidence_type
        self.company = company
        self.role = role
        self.duration = duration

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "evidence_id": self.evidence_id,
            "skill": self.skill,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "description": self.description,
            "confidence": self.confidence,
            "evidence_type": self.evidence_type,
        }
        if self.evidence_type == "project":
            d["project_id"] = self.project_id
            d["project_name"] = self.project_name
        else:
            d["company"] = self.company
            d["role"] = self.role
            d["duration"] = self.duration
        return d


def _make_evidence_id(skill: str, name: str, idx: int) -> str:
    """Generate a deterministic evidence ID from skill + source name."""
    raw = f"{skill}:{name}:{idx}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"EV-{short_hash}"


# ---------------------------------------------------------------------------
# FalkorDB evidence retrieval (reuses existing repository_cypher)
# ---------------------------------------------------------------------------

def _retrieve_falkor(candidate_id: str, matched_skills: List[str]) -> List[EvidenceItem]:
    """Retrieve evidence via FalkorDB using existing Cypher queries."""
    from career_graph.repository_cypher import evidence_for_skill_for_candidate

    res = evidence_for_skill_for_candidate(str(candidate_id), matched_skills)
    evidence_items: List[EvidenceItem] = []
    idx = 0

    for row in res.result_set:
        skill_name = row[0]
        project_evidence = [p for p in row[1] if p.get("name") is not None]
        experience_evidence = [e for e in row[2] if e.get("role") is not None or e.get("company") is not None]

        for proj in project_evidence:
            idx += 1
            ev_id = _make_evidence_id(skill_name, proj.get("name", ""), idx)
            evidence_items.append(EvidenceItem(
                evidence_id=ev_id,
                skill=skill_name,
                project_id=proj.get("name", ""),  # FalkorDB uses name as key
                project_name=proj.get("name", ""),
                source_type="github" if proj.get("url", "").startswith("http") else "project",
                source_url=proj.get("url"),
                description=proj.get("description"),
                confidence=0.9 if proj.get("commits", 0) > 5 else 0.7,
                evidence_type="project",
            ))

        for exp in experience_evidence:
            idx += 1
            ev_id = _make_evidence_id(skill_name, exp.get("company", ""), idx)
            evidence_items.append(EvidenceItem(
                evidence_id=ev_id,
                skill=skill_name,
                source_type="experience",
                description=f"{exp.get('role', '')} at {exp.get('company', '')}",
                confidence=0.85,
                evidence_type="experience",
                company=exp.get("company"),
                role=exp.get("role"),
                duration=exp.get("duration"),
            ))

    return evidence_items


# ---------------------------------------------------------------------------
# SQLite evidence retrieval (reuses existing repository + direct queries)
# ---------------------------------------------------------------------------

def _retrieve_sqlite(candidate_id: int, matched_skills: List[str]) -> List[EvidenceItem]:
    """Retrieve evidence via SQLite using direct SQLAlchemy queries."""
    from sqlalchemy import select as sa_select

    evidence_items: List[EvidenceItem] = []
    idx = 0

    with get_session() as session:
        cand = session.get(Candidate, candidate_id)
        if not cand:
            log.warning("[GRAPH] Candidate %s not found in SQLite", candidate_id)
            return []

        # Build skill name → id mapping for target skills
        cand_skills = {s.canonical_name.lower(): s for s in cand.skills}

        # Get all projects for this candidate with their skills
        projects_q = (
            sa_select(Project, Skill.canonical_name)
            .join(project_skill, Project.id == project_skill.c.project_id)
            .join(Skill, Skill.id == project_skill.c.skill_id)
            .where(Project.candidate_id == candidate_id)
        )
        proj_rows = session.execute(projects_q).all()

        # Index: skill_lower → list of (Project, skill_name)
        proj_by_skill: Dict[str, List] = {}
        for proj, skill_name in proj_rows:
            proj_by_skill.setdefault(skill_name.lower(), []).append(proj)

        # Get experiences for this candidate
        exps = session.scalars(
            sa_select(Experience).where(Experience.candidate_id == candidate_id)
        ).all()

        # Iterate over matched skills and gather evidence
        for skill in matched_skills:
            skill_lower = skill.lower()

            # Project evidence
            seen_proj_ids = set()
            for proj in proj_by_skill.get(skill_lower, []):
                if proj.id in seen_proj_ids:
                    continue
                seen_proj_ids.add(proj.id)
                idx += 1
                ev_id = _make_evidence_id(skill, proj.name or "", idx)
                evidence_items.append(EvidenceItem(
                    evidence_id=ev_id,
                    skill=skill,
                    project_id=str(proj.id),
                    project_name=proj.name,
                    source_type="github" if (proj.url or "").startswith("http") else "project",
                    source_url=proj.url,
                    description=proj.description,
                    confidence=0.9 if (proj.commit_count or 0) > 5 else 0.7,
                    evidence_type="project",
                ))

            # Experience evidence
            for exp in exps:
                if exp.description and skill_lower in exp.description.lower():
                    idx += 1
                    ev_id = _make_evidence_id(skill, exp.company or "", idx)
                    duration = f"{exp.start_date or ''} - {exp.end_date or ''}"
                    evidence_items.append(EvidenceItem(
                        evidence_id=ev_id,
                        skill=skill,
                        source_type="experience",
                        description=f"{exp.title} at {exp.company}",
                        confidence=0.85,
                        evidence_type="experience",
                        company=exp.company,
                        role=exp.title,
                        duration=duration,
                    ))

    return evidence_items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_evidence(candidate_id, matched_skills: List[str]) -> List[EvidenceItem]:
    """Retrieve grounded evidence for matched skills from the candidate's knowledge graph.

    Automatically selects FalkorDB or SQLite based on the active backend.

    Args:
        candidate_id: Candidate identifier (int for SQLite, str for FalkorDB).
        matched_skills: List of canonical skill names to find evidence for.

    Returns:
        List of EvidenceItem objects, each with a unique evidence_id.
    """
    if not matched_skills:
        log.info("[GRAPH] No matched skills — skipping evidence retrieval")
        return []

    backend = get_active_backend()
    log.info("[GRAPH] Retrieving evidence via %s for %d skills", backend, len(matched_skills))

    if backend == "falkor":
        try:
            items = _retrieve_falkor(str(candidate_id), matched_skills)
            log.info("[GRAPH] Retrieved %d evidence items from FalkorDB", len(items))
            return items
        except Exception as e:
            log.warning("[GRAPH] FalkorDB evidence retrieval failed (%s); falling back to SQLite", e)

    # SQLite fallback
    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
    except ValueError:
        cand_id_int = 1

    items = _retrieve_sqlite(cand_id_int, matched_skills)
    log.info("[GRAPH] Retrieved %d evidence items from SQLite", len(items))
    return items


def evidence_by_skill(evidence_items: List[EvidenceItem]) -> Dict[str, List[Dict]]:
    """Group evidence items by skill name — useful for context building."""
    grouped: Dict[str, List[Dict]] = {}
    for item in evidence_items:
        grouped.setdefault(item.skill, []).append(item.to_dict())
    return grouped


class EvidenceRetrievalService:
    """Service wrapper for evidence retrieval."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def retrieve_evidence_for_skills(self, skills: List[str], candidate_id: Any = 1) -> Dict[str, Any]:
        """Retrieve and format evidence report for a list of skills."""
        items = retrieve_evidence(candidate_id, skills)
        grouped = evidence_by_skill(items)
        report = {}
        for skill in skills:
            report[skill] = {
                "skill": skill,
                "evidence": grouped.get(skill, []),
            }
        return report

