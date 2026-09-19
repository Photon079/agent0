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


class GithubIngestPayload(BaseModel):
    username: str
    token: Optional[str] = None
    max_repos: int = 100


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


# ---------------- List endpoints (used by frontend) ----------------

@app.get("/candidates")
def list_candidates():
    """List all candidates with skill count and project count."""
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from career_graph.db import get_session
    from career_graph.models import Candidate, Project

    with get_session() as session:
        candidates = session.scalars(
            select(Candidate).options(selectinload(Candidate.skills))
        ).all()
        result = []
        for c in candidates:
            skill_names = [s.canonical_name for s in c.skills]  # eagerly loaded
            proj_count = session.scalar(
                select(func.count()).select_from(Project).where(Project.candidate_id == c.id)
            ) or 0
            result.append({
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "skills": skill_names,
                "project_count": proj_count,
            })
        return result


@app.get("/jobs")
def list_jobs():
    """List all job postings with required skills."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from career_graph.db import get_session
    from career_graph.models import JobPosting

    with get_session() as session:
        jobs = session.scalars(
            select(JobPosting).options(selectinload(JobPosting.skills))
        ).all()
        return [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "url": j.url,
                "description": j.description,
                "skills": [s.canonical_name for s in j.skills],  # eagerly loaded
            }
            for j in jobs
        ]


@app.post("/ingest/github")
def ingest_github(payload: GithubIngestPayload):
    """Trigger full GitHub username ingestion (fetches repos, extracts skills, writes graph)."""
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from career_graph.db import get_session
    from career_graph.models import Candidate, Project
    from career_graph.ingestion.candidate_ingestor import CandidateIngestor

    ingestor = CandidateIngestor()
    token = payload.token or os.getenv("GITHUB_TOKEN")
    cand = ingestor.ingest_github_username(payload.username, token=token, max_repos=payload.max_repos)
    cand_id = cand.id
    cand_name = cand.name

    # Re-query inside a fresh session to safely access relationships
    with get_session() as session:
        c = session.scalar(
            select(Candidate).where(Candidate.id == cand_id).options(selectinload(Candidate.skills))
        )
        proj_count = session.scalar(
            select(func.count()).select_from(Project).where(Project.candidate_id == cand_id)
        ) or 0
        return {
            "candidate_id": cand_id,
            "name": cand_name,
            "skills": [s.canonical_name for s in c.skills] if c else [],
            "project_count": proj_count,
        }


class ScrapeJobsPayload(BaseModel):
    sources: List[str] = ["remoteok", "arbeitnow", "adzuna"]
    limit: int = 20


@app.post("/scrape/jobs")
def scrape_jobs(payload: ScrapeJobsPayload):
    """Scrape live job postings and write them into the graph.

    Runs the scraper pipeline (remoteok, arbeitnow, etc.) then immediately
    processes the results into JobPosting + REQUIRES edges — no CLI needed.
    """
    from career_graph.scraper.pipeline import scrape
    from career_graph.ingestion.job_processor import JobProcessor

    # 1. Scrape live jobs
    try:
        jobs_raw = scrape(limit_per_source=payload.limit, sources=payload.sources)
    except Exception as e:
        return {"error": f"Scrape failed: {e}", "scraped": 0, "added": 0}

    # 2. Process each job into the graph
    processor = JobProcessor()
    added, errors = 0, 0
    for job in jobs_raw:
        try:
            processor.process(job)
            added += 1
        except Exception:
            errors += 1

    return {
        "scraped": len(jobs_raw),
        "added": added,
        "errors": errors,
        "sources": payload.sources,
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


class UnifiedIngestPayload(BaseModel):
    github_username: Optional[str] = None
    github_token: Optional[str] = None
    resume_text: Optional[str] = None


@app.post("/ingest/unified")
async def ingest_unified(
    github_username: Optional[str] = Form(None),
    github_token: Optional[str] = Form(None),
    resume_text: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None)
):
    """Unified endpoint to ingest both GitHub and Resume into a single Candidate profile."""
    from career_graph.ingestion.candidate_ingestor import CandidateIngestor
    
    candidate = None
    
    # 1. Parse Resume if provided
    raw_resume = ""
    if resume_file:
        raw_resume = (await resume_file.read()).decode("utf-8")
    elif resume_text:
        raw_resume = resume_text

    if raw_resume:
        parsed_resume = resume_parser.parse(raw_resume)
        if parsed_resume:
            candidate = gw.write_parsed_candidate(parsed_resume)
            
    # 2. Ingest GitHub if provided
    if github_username:
        ingestor = CandidateIngestor()
        token = github_token or os.getenv("GITHUB_TOKEN")
        
        # If candidate already created from resume, we can use their name/id context
        # But ingestor.ingest_github_username handles upsert_candidate internally
        # which will now match by name thanks to our GraphWriter update!
        gh_candidate = ingestor.ingest_github_username(github_username, token=token, max_repos=100)
        if not candidate:
            candidate = gh_candidate
            
    if not candidate:
        return {"error": "No valid data provided to ingest"}
        
    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "email": candidate.email
    }


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


@app.get("/gap/{candidate_id}/{job_id}/project")
def gap_project(candidate_id: str, job_id: str):
    from career_graph.extraction.bedrock import suggest_micro_project
    from career_graph.db import get_session
    from career_graph.models import Candidate, JobPosting

    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
        job_id_int = int(str(job_id).replace("job:", ""))
    except ValueError:
        return {"error": "Invalid ID format"}

    with get_session() as session:
        cand = session.get(Candidate, cand_id_int)
        job = session.get(JobPosting, job_id_int)
        if not cand or not job:
            return {"error": "Candidate or Job not found"}
        
        cand_skills = [s.canonical_name for s in cand.skills]
        job_skills = [s.canonical_name for s in job.skills]
        
        missing = [s for s in job_skills if s not in cand_skills]
        if not missing:
            return {"title": "No Gap Detected", "description": "You already have all the required skills for this job!"}
            
        suggestion = suggest_micro_project(job_skills, missing, cand_skills)
        return suggestion


from pydantic import BaseModel
class BulletGenerateRequest(BaseModel):
    candidate_id: str
    job_id: str

@app.post("/generate/bullets")
def generate_bullets(req: BulletGenerateRequest):
    from career_graph.extraction.bedrock import generate_proof_bullets
    from career_graph.db import get_session
    from career_graph.models import Candidate, JobPosting

    try:
        cand_id_int = int(str(req.candidate_id).replace("cand:", ""))
        job_id_int = int(str(req.job_id).replace("job:", ""))
    except ValueError:
        return {"error": "Invalid ID format"}

    with get_session() as session:
        cand = session.get(Candidate, cand_id_int)
        job = session.get(JobPosting, job_id_int)
        if not cand or not job:
            return {"error": "Candidate or Job not found"}
        
        cand_skills = [s.canonical_name for s in cand.skills]
        job_skills = [s.canonical_name for s in job.skills]
        overlap = [s for s in job_skills if s in cand_skills]
    
    if not overlap:
        return {"bullets": []}
    
    # Get evidence for overlapping skills
    ev_res = evidence_candidate(req.candidate_id, skills=",".join(overlap))
    evidence_list = ev_res.get("evidence", [])
    
    bullets = generate_proof_bullets(job.title, evidence_list)
    return {"bullets": bullets}


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

    # SQLite fallback — use explicit SQL joins so lazy-loading session scope issues
    # don't produce empty project_evidence arrays.
    try:
        cand_id_int = int(str(candidate_id).replace("cand:", ""))
    except ValueError:
        cand_id_int = 1
    from sqlalchemy import select as sa_select
    from career_graph.db import get_session
    from career_graph.models import Candidate, Project, Skill, Experience, project_skill, candidate_skill

    with get_session() as session:
        cand = session.get(Candidate, cand_id_int)
        if not cand:
            return {"candidate_id": candidate_id, "evidence": [], "backend": "sqlite"}

        # candidate's own skills
        cand_skills = [s.canonical_name for s in cand.skills]
        target_skills = skill_list or cand_skills

        # explicit project query: projects owned by this candidate + their skills
        projects_q = (
            sa_select(Project, Skill.canonical_name)
            .join(project_skill, Project.id == project_skill.c.project_id)
            .join(Skill, Skill.id == project_skill.c.skill_id)
            .where(Project.candidate_id == cand_id_int)
        )
        proj_rows = session.execute(projects_q).all()
        # build index: skill_name → list of project evidence dicts
        proj_by_skill: dict = {}
        for proj, skill_name in proj_rows:
            sk_lower = skill_name.lower()
            proj_by_skill.setdefault(sk_lower, [])
            # deduplicate by project id
            if not any(e["_pid"] == proj.id for e in proj_by_skill[sk_lower]):
                proj_by_skill[sk_lower].append({
                    "_pid": proj.id,
                    "type": "project",
                    "name": proj.name,
                    "description": proj.description,
                    "commits": proj.commit_count,
                    "url": proj.url,
                })

        # explicit experience query
        exps = session.scalars(
            sa_select(Experience).where(Experience.candidate_id == cand_id_int)
        ).all()

        evidence_out = []
        for sname in target_skills:
            p_ev = [{k: v for k, v in e.items() if k != "_pid"} for e in proj_by_skill.get(sname.lower(), [])]
            e_ev = []
            for exp in exps:
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