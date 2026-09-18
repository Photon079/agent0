"""Tests for CandidateIngestor (resume text + github repos) into the graph."""
from sqlalchemy import select

from career_graph import models
from career_graph.db import get_session
from career_graph.ingestion.candidate_ingestor import CandidateIngestor


RESUME = """Jane Doe
jane@example.com

Python Developer with AWS expertise.
https://github.com/jane/awesome-project
"""

GITHUB_REPOS = [
    {"name": "pipeline", "html_url": "https://github.com/u/pipeline", "description": "etl", "language": "Python", "commits_count": 30, "readme_text": "# pipeline\nBuilt with FastAPI and Pandas."},
    {"name": "web", "html_url": "https://github.com/u/web", "description": "site", "language": "TypeScript", "commits_count": 12, "readme_text": "# web\nReact frontend served on AWS."},
]


def test_ingest_resume_text():
    cand = CandidateIngestor().ingest_resume_text(RESUME)
    assert cand.name == "Jane Doe"
    with get_session() as session:
        skills = [s.canonical_name for s in session.scalars(select(models.Skill)).all()]
        projects = list(session.scalars(select(models.Project)).all())
    assert "Python" in skills
    assert "AWS" in skills
    assert any(p.name == "awesome-project" for p in projects)


def test_ingest_github_repos():
    cand = CandidateIngestor().ingest_github_repos(GITHUB_REPOS, name="janedoe")
    assert cand.name == "janedoe"
    with get_session() as session:
        skills = [s.canonical_name for s in session.scalars(select(models.Skill)).all()]
        projects = list(session.scalars(select(models.Project)).all())
    assert "Python" in skills
    assert {"pipeline", "web"} <= {p.name for p in projects}
    assert all(p.candidate_id == cand.id for p in projects)
    # project skill links exist
    with get_session() as session:
        edges = session.execute(select(models.project_skill)).all()
    assert len(edges) >= 2
    # commit counts preserved
    assert {p.name: p.commit_count for p in projects}["pipeline"] == 30


def test_ingest_github_username_empty_repos():
    from career_graph.ingestion import github_fetcher as gf

    orig = gf.fetch_github_repos
    gf.fetch_github_repos = lambda username, token=None, max_repos=10: []
    try:
        import pytest

        with pytest.raises(RuntimeError):
            CandidateIngestor().ingest_github_username("ghost")
    finally:
        gf.fetch_github_repos = orig