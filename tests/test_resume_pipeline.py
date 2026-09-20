"""Unit & Integration Tests for Graph-Grounded Resume Tailoring Pipeline."""

import pytest
from fastapi.testclient import TestClient

from career_graph.db import get_session
from career_graph.models import Candidate, JobPosting, Skill, Experience, Project
from career_graph.resume import (
    EvidenceRetrievalService,
    ResumeContextBuilder,
    ResumeTailoringAgent,
    GroundingValidator,
    LatexRenderer,
    ResumePipelineOrchestrator,
    escape_latex,
)
from career_graph.api.app import app


@pytest.fixture
def sample_candidate_data():
    return {
        "id": 1,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "location": "San Francisco, CA",
        "experience_level": "Senior",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "PyTorch"],
        "experiences": [
            {
                "title": "Senior Backend Engineer",
                "company": "Tech Corp",
                "start_date": "2021-01",
                "end_date": "Present",
                "description": "Built high-performance microservices in Python with FastAPI and PostgreSQL. Scaled architecture to 10M API requests per day.",
            }
        ],
        "projects": [
            {
                "name": "AI Pipeline Framework",
                "description": "Open-source data processing engine built with Python and PyTorch. Containerized with Docker.",
                "url": "https://github.com/janedoe/ai-pipeline",
                "commits_count": 45,
                "skills": ["Python", "PyTorch", "Docker"],
            }
        ],
    }


@pytest.fixture
def sample_job_description():
    return {
        "id": 101,
        "title": "Senior AI Backend Engineer",
        "company": "Innovate AI",
        "description": "Looking for a Senior Python engineer to build LLM pipelines with FastAPI, PyTorch, and Docker on AWS.",
        "required_skills": ["Python", "FastAPI", "PyTorch", "Docker", "AWS", "Kubernetes"],
        "experience_level": "Senior",
        "location": "Remote",
    }


@pytest.fixture
def db_candidate_and_job():
    """Populate isolated temp DB with candidate and job records."""
    with get_session() as session:
        s1 = Skill(canonical_name="Python")
        s2 = Skill(canonical_name="FastAPI")
        session.add_all([s1, s2])
        session.flush()

        cand = Candidate(name="Jane Doe", email="jane@example.com", skills=[s1, s2])
        session.add(cand)

        job = JobPosting(title="Senior Backend Engineer", company="Tech Corp", description="Python FastAPI role", skills=[s1, s2])
        session.add(job)
        session.commit()

        return cand.id, job.id


# --- Phase 1: Evidence Retrieval ---
def test_evidence_retrieval(db_candidate_and_job):
    cand_id, _ = db_candidate_and_job
    service = EvidenceRetrievalService()
    skills = ["Python", "FastAPI"]
    report = service.retrieve_evidence_for_skills(skills, candidate_id=cand_id)
    assert isinstance(report, dict)
    assert "Python" in report
    assert "FastAPI" in report


# --- Phase 2: ResumeContext Builder ---
def test_resume_context_builder(sample_candidate_data, sample_job_description):
    builder = ResumeContextBuilder()
    ctx = builder.build_context(
        candidate_data=sample_candidate_data,
        job_description=sample_job_description,
    )
    assert ctx["candidate"]["name"] == "Jane Doe"
    assert ctx["target_job"]["title"] == "Senior AI Backend Engineer"
    assert "matched_evidence" in ctx
    assert len(ctx["experiences"]) == 1


# --- Phase 3: Tailoring Agent ---
def test_tailoring_agent_fallback(sample_candidate_data, sample_job_description):
    builder = ResumeContextBuilder()
    ctx = builder.build_context(
        candidate_data=sample_candidate_data,
        job_description=sample_job_description,
    )
    agent = ResumeTailoringAgent()
    # Test deterministic fallback
    res = agent._generate_fallback(ctx)
    assert res["candidate"]["name"] == "Jane Doe"
    assert "skills" in res
    assert len(res["experience"]) == 1


# --- Phase 4: Grounding Validator ---
def test_grounding_validator(sample_candidate_data, sample_job_description):
    builder = ResumeContextBuilder()
    ctx = builder.build_context(
        candidate_data=sample_candidate_data,
        job_description=sample_job_description,
    )
    agent = ResumeTailoringAgent()
    res_json = agent._generate_fallback(ctx)

    validator = GroundingValidator()
    report = validator.validate(res_json, ctx)

    assert "grounding_score" in report
    assert report["grounding_score"] >= 0.70
    assert "ungrounded_claims" in report


def test_grounding_validator_detects_hallucination(sample_candidate_data, sample_job_description):
    builder = ResumeContextBuilder()
    ctx = builder.build_context(
        candidate_data=sample_candidate_data,
        job_description=sample_job_description,
    )

    # Fabricate hallucinatory resume JSON
    fake_json = {
        "name": "Jane Doe",
        "skills": [{"category": "Languages", "items": ["Rust", "Haskell"]}],  # Not in context
        "experience": [
            {
                "company": "Fake Corp 999",  # Fake company
                "title": "CTO",
                "bullets": ["Increased revenue by $500M with quantum computing."],  # Fabricated metric
            }
        ],
        "projects": [],
    }

    validator = GroundingValidator()
    report = validator.validate(fake_json, ctx)

    assert report["is_valid"] is False
    assert len(report["ungrounded_claims"]) > 0


# --- Phase 5: LaTeX Renderer ---
def test_latex_escape():
    raw = "Working with C++ & C# & 100% test coverage in $USD!"
    escaped = escape_latex(raw)
    assert r"\&" in escaped
    assert r"\%" in escaped
    assert r"\$" in escaped


def test_latex_renderer(sample_candidate_data, sample_job_description):
    builder = ResumeContextBuilder()
    ctx = builder.build_context(
        candidate_data=sample_candidate_data,
        job_description=sample_job_description,
    )
    agent = ResumeTailoringAgent()
    res_json = agent._generate_fallback(ctx)

    renderer = LatexRenderer()
    tex_code = renderer.render_tex(res_json)

    assert r"\documentclass" in tex_code
    assert "Jane Doe" in tex_code
    assert r"\end{document}" in tex_code


# --- Phase 6: Orchestrator End-to-End ---
def test_orchestrator_end_to_end(sample_candidate_data, sample_job_description, tmp_path):
    orchestrator = ResumePipelineOrchestrator()
    res = orchestrator.run_pipeline(
        candidate_data=sample_candidate_data,
        job_description=sample_job_description,
        output_dir=str(tmp_path),
        output_filename="test_resume"
    )

    assert res["status"] in ["SUCCESS", "WARNING"]
    assert "resume_json" in res
    assert "latex_code" in res
    assert res["tex_file"].endswith(".tex")


# --- API Endpoint Test ---
def test_api_tailor_resume_endpoint(db_candidate_and_job):
    cand_id, job_id = db_candidate_and_job
    client = TestClient(app)
    response = client.post(
        "/tailor-resume",
        json={
            "candidate_id": str(cand_id),
            "job_id": str(job_id),
            "output_filename": "api_test_resume"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "resume_json" in data
    assert "latex_code" in data
    assert "validation" in data
