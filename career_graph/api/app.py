from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List

from career_graph.graph_writer import GraphWriter
from career_graph.parsers.simple_resume_parser import SimpleResumeParser
from career_graph.parsers.github_parser import GithubParser
from career_graph.parsers.job_parser import JobParser

app = FastAPI(title="Career Graph API")
gw = GraphWriter()
resume_parser = SimpleResumeParser()
github_parser = GithubParser()
job_parser = JobParser()


class GithubPayload(BaseModel):
    repos: List[dict]
    name: Optional[str] = None
    email: Optional[str] = None


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


# ---------------- Query ----------------

@app.get("/match/{candidate_id}")
def match_jobs(candidate_id: int):
    from career_graph.repository import match_jobs_by_skill_overlap

    rows = match_jobs_by_skill_overlap(candidate_id)
    return [{"job": r[0].title, "company": r[0].company, "overlap": int(r[1])} for r in rows]


@app.get("/gap/{candidate_id}/{job_id}")
def gap(candidate_id: int, job_id: int):
    from career_graph.repository import gap_detection

    missing = gap_detection(candidate_id, job_id)
    return {"missing_skills": missing}


@app.get("/evidence/skill/{skill_id}")
def evidence_skill(skill_id: int):
    from career_graph.repository import evidence_for_skill

    return evidence_for_skill(skill_id)