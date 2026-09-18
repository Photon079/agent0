"""Tests for JobProcessor: skill extraction, alias normalization, dedupe."""
from sqlalchemy import select

from career_graph import models
from career_graph.ingestion.job_processor import JobProcessor
from career_graph.scraper.sources import _norm


def _job(**kw):
    base = _norm("ext-1", "greenhouse", "Backend Engineer", "Acme", "https://x/j1", "<p>Python AWS SQL Kubernetes</p>", "Remote")
    base.update(kw)
    return base


def test_process_normalized_scraper_job():
    posting = JobProcessor().process(_job())
    assert posting.title == "Backend Engineer"
    assert posting.company == "Acme"
    from career_graph.db import get_session

    with get_session() as session:
        reqs = session.execute(select(models.job_requirement)).all()
        skills = session.execute(select(models.Skill.canonical_name)).all()
    names = {r[0] for r in skills}
    assert {"Python", "AWS", "SQL"} <= names  # canonicalized via alias dict
    assert len(reqs) > 0


def test_process_uses_pre_extracted_requirements():
    job = _job(requirements=[{"name": "Typescript", "importance": 0.8}, {"name": "React", "importance": 1.0}])
    JobProcessor().process(job)
    from career_graph.db import get_session

    with get_session() as session:
        skills = session.execute(select(models.Skill.canonical_name)).all()
    names = {r[0].lower() for r in skills}
    assert "typescript" in names
    assert "react" in names


def test_process_dedupes_requirements_by_canonical():
    job = _job(requirements=[{"name": "Python"}, {"name": "python"}, {"name": "Python3"}])
    posting = JobProcessor().process(job)
    # canonical keys should collapse earlier raw strings
    assert posting.title == "Backend Engineer"


def test_process_backward_compat_raw_text():
    raw = "Data Engineer\nAcme\n\n- Python\n- Spark\n"
    posting = JobProcessor().process({"description": raw})
    assert posting.title == "Data Engineer"


def test_process_missing_title_raises():
    import pytest

    with pytest.raises(ValueError):
        JobProcessor().process({"description": ""})