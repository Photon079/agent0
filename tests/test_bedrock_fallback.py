"""Tests for the extraction module's Bedrock-to-heuristic fallback behavior.

Defaults to heuristic since CAREER_GRAPH_USE_BEDROCK is not set in tests.
The Bedrock path is exercised with a failing client to prove graceful fallback.
"""
import importlib

from career_graph.extraction import bedrock


def test_extract_resume_heuristic():
    parsed = bedrock.extract_resume("John Smith\njohn@x.com\n\nAWS and Python expert.")
    assert parsed["name"] == "John Smith"
    assert parsed["email"] == "john@x.com"
    assert {"Python", "AWS"} <= {s["canonical_name"] for s in parsed["skills"]}


def test_extract_job_skills_heuristic():
    out = bedrock.extract_job_skills("Backend Engineer\n\n- Python\n- AWS\n- Kubernetes")
    names = {s["canonical_name"] for s in out["skills"]}
    assert "Python" in names
    assert "Kubernetes" in names


def test_extract_github_heuristic():
    repos = [{"name": "app", "html_url": "x", "description": "d", "language": "Go", "commits_count": 5, "readme_text": ""}]
    parsed = bedrock.extract_github_repos(repos)
    assert parsed["projects"][0]["skills"] == ["Go"]


def test_bedrock_enabled_falls_back_on_failure(monkeypatch):
    import os

    monkeypatch.setenv("CAREER_GRAPH_USE_BEDROCK", "1")
    monkeypatch.setenv("BEDROCK_DEBUG", "1")
    importlib.reload(bedrock)
    assert bedrock.USE_BEDROCK is True

    def _boom(system, user, model, max_tokens=2048):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(bedrock, "_converse", _boom)
    parsed = bedrock.extract_resume("Alex Lee\n# Python\n")
    assert parsed["name"]  # heuristic fallback ran
    out = bedrock.extract_job_skills("Python AWS SQL")
    assert out["skills"]
    try:
        parsed = bedrock.extract_github_repos([{"name": "r", "readme_text": "x", "language": "Rust"}])
        assert parsed["projects"][0]["skills"] == ["Rust"]
    finally:
        monkeypatch.delenv("CAREER_GRAPH_USE_BEDROCK")
        monkeypatch.delenv("BEDROCK_DEBUG")
        importlib.reload(bedrock)
        assert bedrock.USE_BEDROCK is False