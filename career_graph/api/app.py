import logging
import os
from typing import List, Optional
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from career_graph.backend import get_active_backend
from career_graph.graph_writer import GraphWriter
from career_graph.parsers.github_parser import GithubParser
from career_graph.parsers.job_parser import JobParser
from career_graph.parsers.simple_resume_parser import SimpleResumeParser

log = logging.getLogger(__name__)

app = FastAPI(title="Career Graph API")

# Enable CORS for local React/Vite dev and Amplify hosting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to Amplify domain post-hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gw = GraphWriter()
resume_parser = SimpleResumeParser()
github_parser = GithubParser()
job_parser = JobParser()


class GithubPayload(BaseModel):
    repos: List[dict]
    name: Optional[str] = None
    email: Optional[str] = None


# ---------------- Health & Backend ----------------

@app.get("/backend")
def get_backend_status():
    """Return active and configured graph engine (falkor vs sqlite)."""
    from career_graph.backend import is_falkor_available

    return {
        "active_backend": get_active_backend(),
        "configured_backend": os.getenv("CAREER_GRAPH_BACKEND") or "default (auto-detect)",
        "falkordb_available": is_falkor_available(),
    }


# ---------------- Ingestion ----------------

@app.post("/parse/resume")
async def parse_resume(text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    if file is not None:
        raw = (await file.read()).decode("utf-8")
    else:
        raw = text or ""

    parsed = resume_parser.parse(raw)
    cand = gw.write_parsed_candidate(parsed)
    return {"candidate_id": cand.id, "name": cand.name}


@app.post("/parse/github")
async def parse_github(payload: GithubPayload):
    parsed = github_parser.parse(payload.repos)
    candidate = None
    if payload.email:
        candidate = gw.upsert_candidate(payload.name or "", payload.email)

    created = []
    for p in parsed.get("projects", []):
        proj = gw.upsert_project(p.get("name"), description=p.get("description"), url=p.get("url"), commit_count=p.get("commit_count", 0), source="github", candidate_id=(candidate.id if candidate else None))
        for sk_name in p.get("skills", []):
            if sk_name:
                sk = gw.upsert_skill(sk_name)
                gw.link_project_skill(proj.id, sk.id)
        created.append({"project_id": proj.id, "name": proj.name})
    return {"projects": created}


@app.post("/parse/job")
async def parse_job(text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    if file is not None:
        raw = (await file.read()).decode("utf-8")
    else:
        raw = text or ""

    parsed = job_parser.parse(raw)
    job = gw.upsert_jobposting(parsed.get("title"), parsed.get("company"), parsed.get("description"), source="api")
    for s in parsed.get("skills", []):
        sk = gw.upsert_skill(s.get("canonical_name"))
        gw.link_job_requirement(job.id, sk.id, importance=s.get("importance", 1.0))

    return {"job_id": job.id, "title": job.title}


# ---------------- Query (Active Backend: FalkorDB / SQLite) ----------------

@app.get("/match/{candidate_id}")
def match_jobs(candidate_id: str, limit: int = 10):
    backend = get_active_backend()
    if backend == "falkor":
        try:
            from career_graph.repository_cypher import match_jobs_by_skill_overlap

            res = match_jobs_by_skill_overlap(str(candidate_id), limit=limit)
            return [{"job": r[1], "company": r[2], "overlap": int(r[4])} for r in res.result_set]
        except Exception as e:
            log.warning("FalkorDB match query failed (%s); falling back to SQLite", e)

    # SQLite fallback / default
    from career_graph.repository import match_jobs_by_skill_overlap

    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
    except ValueError:
        cand_id_int = 1
    rows = match_jobs_by_skill_overlap(cand_id_int, limit=limit)
    return [{"job": r[0].title, "company": r[0].company, "overlap": int(r[1])} for r in rows]


@app.get("/gap/{candidate_id}/{job_id}")
def gap(candidate_id: str, job_id: str):
    backend = get_active_backend()
    if backend == "falkor":
        try:
            from career_graph.repository_cypher import gap_detection

            res = gap_detection(str(candidate_id), str(job_id))
            missing = [r[0] for r in res.result_set]
            return {"missing_skills": missing}
        except Exception as e:
            log.warning("FalkorDB gap query failed (%s); falling back to SQLite", e)

    # SQLite fallback / default
    from career_graph.repository import gap_detection

    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
        job_id_int = int(str(job_id).replace("job:", ""))
    except ValueError:
        return {"missing_skills": []}
    missing = gap_detection(cand_id_int, job_id_int)
    return {"missing_skills": missing}


@app.get("/evidence/skill/{skill_id}")
def evidence_skill(skill_id: str):
    backend = get_active_backend()
    if backend == "falkor":
        try:
            from career_graph.repository_cypher import evidence_for_skill

            return evidence_for_skill(str(skill_id))
        except Exception as e:
            log.warning("FalkorDB evidence query failed (%s); falling back to SQLite", e)

    # SQLite fallback / default
    from career_graph.repository import evidence_for_skill

    try:
        sk_id_int = int(skill_id)
        return evidence_for_skill(sk_id_int)
    except ValueError:
        from sqlalchemy import select
        from career_graph.db import get_session
        from career_graph.models import Skill

        with get_session() as session:
            sk = session.scalars(select(Skill).where(Skill.canonical_name.ilike(skill_id))).first()
            if sk:
                return evidence_for_skill(sk.id)
            return {"projects": [], "candidates": [], "experiences": []}


@app.get("/evidence/candidate/{candidate_id}")
def evidence_candidate(candidate_id: str, skills: Optional[str] = None):
    """Retrieve grounded evidence (projects + corporate experiences) for candidate skills."""
    skill_list = [s.strip() for s in skills.split(",")] if skills else []
    backend = get_active_backend()
    if backend == "falkor":
        try:
            from career_graph.repository_cypher import evidence_for_skill_for_candidate, query

            if not skill_list:
                cand_res = query(
                    "MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill) WHERE c.id = $cid OR c.id = 'cand:' + $cid RETURN s.canonical_name",
                    {"cid": str(candidate_id)},
                )
                skill_list = [r[0] for r in cand_res.result_set]

            res = evidence_for_skill_for_candidate(str(candidate_id), skill_list)
            evidence_out = []
            for row in res.result_set:
                projs = [p for p in row[1] if p.get("name") is not None]
                exps = [e for e in row[2] if e.get("role") is not None or e.get("company") is not None]
                evidence_out.append({
                    "skill": row[0],
                    "project_evidence": projs,
                    "experience_evidence": exps,
                })
            return {"candidate_id": candidate_id, "evidence": evidence_out, "backend": "falkor"}
        except Exception as e:
            log.warning("FalkorDB candidate evidence query failed (%s); falling back to SQLite", e)

    # SQLite fallback
    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
    except ValueError:
        cand_id_int = 1
    from career_graph.db import get_session
    from career_graph.models import Candidate

    with get_session() as session:
        cand = session.get(Candidate, cand_id_int)
        if not cand:
            return {"candidate_id": candidate_id, "evidence": [], "backend": "sqlite"}
        cand_skills = [s.canonical_name for s in cand.skills]
        target_skills = skill_list or cand_skills
        evidence_out = []
        for sname in target_skills:
            p_ev = []
            for p in cand.projects:
                for sk in p.skills:
                    if sk.canonical_name.lower() == sname.lower():
                        p_ev.append({
                            "type": "project",
                            "name": p.name,
                            "description": p.description,
                            "commits": p.commit_count,
                            "url": p.url,
                        })
            e_ev = []
            for exp in cand.experiences:
                if exp.description and sname.lower() in exp.description.lower():
                    duration = f"{exp.start_date or ''} - {exp.end_date or ''}"
                    e_ev.append({
                        "type": "experience",
                        "role": exp.title,
                        "company": exp.company,
                        "duration": duration,
                    })
            evidence_out.append({
                "skill": sname,
                "project_evidence": p_ev,
                "experience_evidence": e_ev,
            })
        return {"candidate_id": candidate_id, "evidence": evidence_out, "backend": "sqlite"}