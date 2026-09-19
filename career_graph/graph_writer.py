"""GraphWriter: writes parsed entities into the relational backing store
as nodes and edges representing the career knowledge graph.

The writer is intentionally simple: it upserts nodes by natural keys
and creates association rows for edges with properties (confidence, evidence).
"""
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from .db import get_session
from .models import Candidate, Skill, Project, JobPosting, candidate_skill, project_skill, job_requirement
from .normalizer.alias_normalizer import AliasNormalizer


class GraphWriter:
    def __init__(self):
        # instantiate alias normalizer for skill canonicalization
        self.normalizer = AliasNormalizer()

    def upsert_skill(self, canonical_name: str, aliases: Optional[List[str]] = None, category: Optional[str] = None) -> Skill:
        # ensure canonicalization via alias normalizer
        if canonical_name:
            canonical_name = self.normalizer.normalize(canonical_name)

        with get_session() as session:
            stmt = select(Skill).where(Skill.canonical_name == canonical_name)
            skill = session.scalars(stmt).first()
            if skill:
                # update fields if provided
                if aliases is not None:
                    skill.aliases = aliases
                if category is not None:
                    skill.category = category
                session.add(skill)
                session.commit()
                session.refresh(skill)
                return skill

            skill = Skill(canonical_name=canonical_name, aliases=aliases or [], category=category)
            session.add(skill)
            session.commit()
            session.refresh(skill)
            return skill

    def upsert_candidate(self, name: str, email: Optional[str] = None) -> Candidate:
        with get_session() as session:
            if email:
                stmt = select(Candidate).where(Candidate.email == email)
                candidate = session.scalars(stmt).first()
                if candidate:
                    candidate.name = name or candidate.name
                    session.add(candidate)
                    session.commit()
                    session.refresh(candidate)
                    return candidate

            # No email (e.g. GitHub ingestion): deduplicate by name so
            # re-ingesting the same GitHub username doesn't create a new row.
            if name:
                stmt = select(Candidate).where(Candidate.name == name, Candidate.email == None)  # noqa: E711
                candidate = session.scalars(stmt).first()
                if candidate:
                    session.refresh(candidate)
                    return candidate

            candidate = Candidate(name=name, email=email)
            session.add(candidate)
            session.commit()
            session.refresh(candidate)
            return candidate

    def upsert_project(self, name: str, description: Optional[str] = None, url: Optional[str] = None, commit_count: int = 0, source: Optional[str] = None, candidate_id: Optional[int] = None) -> Project:
        with get_session() as session:
            if url:
                stmt = select(Project).where(Project.url == url)
                proj = session.scalars(stmt).first()
                if proj:
                    proj.name = name or proj.name
                    proj.description = description or proj.description
                    proj.commit_count = commit_count or proj.commit_count
                    proj.source = source or proj.source
                    # reassign to the new candidate if provided (re-ingest scenario)
                    if candidate_id is not None:
                        proj.candidate_id = candidate_id
                    session.add(proj)
                    session.commit()
                    session.refresh(proj)
                    return proj

            proj = Project(name=name, description=description, url=url, commit_count=commit_count, source=source, candidate_id=candidate_id)
            session.add(proj)
            session.commit()
            session.refresh(proj)
            return proj

    def upsert_jobposting(self, title: str, company: Optional[str] = None, description: Optional[str] = None, source: Optional[str] = None) -> JobPosting:
        with get_session() as session:
            stmt = select(JobPosting).where(JobPosting.title == title).where(JobPosting.company == company)
            job = session.scalars(stmt).first()
            if job:
                job.description = description or job.description
                session.add(job)
                session.commit()
                session.refresh(job)
                return job

            job = JobPosting(title=title, company=company, description=description, source=source)
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    # Edge/association helpers
    def link_candidate_skill(self, candidate_id: int, skill_id: int, confidence: float = 0.0, evidence: Optional[Dict[str, Any]] = None):
        with get_session() as session:
            exists = session.execute(
                select(candidate_skill).where(candidate_skill.c.candidate_id == candidate_id, candidate_skill.c.skill_id == skill_id)
            ).first()
            if exists:
                return
            session.execute(candidate_skill.insert().values(candidate_id=candidate_id, skill_id=skill_id, confidence=confidence, evidence=evidence))
            session.commit()

    def link_project_skill(self, project_id: int, skill_id: int, evidence: Optional[Dict[str, Any]] = None):
        with get_session() as session:
            exists = session.execute(
                select(project_skill).where(project_skill.c.project_id == project_id, project_skill.c.skill_id == skill_id)
            ).first()
            if exists:
                return
            session.execute(project_skill.insert().values(project_id=project_id, skill_id=skill_id, evidence=evidence))
            session.commit()

    def link_job_requirement(self, job_id: int, skill_id: int, importance: float = 1.0):
        with get_session() as session:
            exists = session.execute(
                select(job_requirement).where(job_requirement.c.job_id == job_id, job_requirement.c.skill_id == skill_id)
            ).first()
            if exists:
                return
            session.execute(job_requirement.insert().values(job_id=job_id, skill_id=skill_id, importance=importance))
            session.commit()

    def write_parsed_candidate(self, parsed: Dict[str, Any]) -> Candidate:
        """Write a parsed candidate dict:

        Expected format:
        {
            "name": str,
            "email": str,
            "skills": [ {"canonical_name":..., "aliases": [...], "confidence": 0.8, "evidence": {...}}, ... ],
            "projects": [ {"name":..., "description":..., "url":..., "commit_count":..., "skills": ["Python"] }, ... ]
        }
        """
        candidate = self.upsert_candidate(parsed.get("name"), parsed.get("email"))

        # skills
        for s in parsed.get("skills", []):
            # enforce alias normalization rule: skill strings must be passed through alias dictionary
            canonical = s.get("canonical_name") or s.get("name") or ""
            canonical = self.normalizer.normalize(canonical)
            skill = self.upsert_skill(canonical, aliases=s.get("aliases"), category=s.get("category"))
            self.link_candidate_skill(candidate.id, skill.id, confidence=s.get("confidence", 0.0), evidence=s.get("evidence"))

        # projects
        for p in parsed.get("projects", []):
            proj = self.upsert_project(p.get("name"), description=p.get("description"), url=p.get("url"), commit_count=p.get("commit_count", 0), source=p.get("source"), candidate_id=candidate.id)
            for skill_name in p.get("skills", []):
                sk_name = self.normalizer.normalize(skill_name)
                sk = self.upsert_skill(sk_name)
                self.link_project_skill(proj.id, sk.id, evidence={"source": p.get("source")})

        return candidate


__all__ = ["GraphWriter"]