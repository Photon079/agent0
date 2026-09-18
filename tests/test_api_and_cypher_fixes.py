import os
from fastapi.middleware.cors import CORSMiddleware
import pytest

from career_graph.api.app import app, match_jobs, gap, evidence_skill, get_backend_status
from career_graph.backend import get_active_backend, is_falkor_available
from career_graph.graph_writer import GraphWriter
from career_graph.repository_cypher import evidence_for_skill_for_candidate


def test_cors_middleware_attached():
    """Verify CORSMiddleware is explicitly attached to app with expected configuration."""
    cors_mw = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert len(cors_mw) >= 1
    kwargs = cors_mw[0].kwargs
    assert "*" in kwargs.get("allow_origins", [])
    assert kwargs.get("allow_credentials") is True
    assert "*" in kwargs.get("allow_methods", [])
    assert "*" in kwargs.get("allow_headers", [])


def test_backend_selection_flag(monkeypatch):
    """Verify CAREER_GRAPH_BACKEND controls backend and falls back to SQLite."""
    # Force SQLite
    monkeypatch.setenv("CAREER_GRAPH_BACKEND", "sqlite")
    assert get_active_backend() == "sqlite"

    status = get_backend_status()
    assert status["active_backend"] == "sqlite"
    assert status["configured_backend"] == "sqlite"

    # When FalkorDB is reachable, setting 'falkor' selects falkor
    if is_falkor_available():
        monkeypatch.setenv("CAREER_GRAPH_BACKEND", "falkor")
        assert get_active_backend() == "falkor"

        status_falkor = get_backend_status()
        assert status_falkor["active_backend"] == "falkor"

        # Default (unset) should also default to falkor when active
        monkeypatch.delenv("CAREER_GRAPH_BACKEND", raising=False)
        assert get_active_backend() == "falkor"


def test_api_endpoints_with_sqlite(monkeypatch):
    """Verify match, gap, and evidence functions work on SQLite."""
    monkeypatch.setenv("CAREER_GRAPH_BACKEND", "sqlite")

    gw = GraphWriter()
    cand = gw.upsert_candidate("Test Runner", "runner@example.com")
    sk_py = gw.upsert_skill("Python")
    gw.link_candidate_skill(cand.id, sk_py.id, confidence=1.0)
    job = gw.upsert_jobposting("Python Dev", "TechCo")
    gw.link_job_requirement(job.id, sk_py.id, importance=1.0)

    # match_jobs
    matches = match_jobs(str(cand.id))
    assert any(j["job"] == "Python Dev" for j in matches)

    # gap
    g = gap(str(cand.id), str(job.id))
    assert "missing_skills" in g

    # evidence_skill
    ev = evidence_skill(str(sk_py.id))
    assert "candidates" in ev


def test_falkor_evidence_retrieval_query_structure():
    """Verify evidence_for_skill_for_candidate traverses both projects and experiences."""
    if not is_falkor_available():
        pytest.skip("FalkorDB is not reachable")

    from career_graph.falkor import query

    # Seed candidate, skill, project, and corporate experience
    cid = "test-corp-cand"
    query("MERGE (c:Candidate {id: $cid})", {"cid": cid})
    query("MERGE (s1:Skill {canonical_name: 'Python'})")
    query("MERGE (s2:Skill {canonical_name: 'Kubernetes'})")

    # Candidate has skill Kubernetes from corporate experience, not project
    query("MATCH (c:Candidate {id: $cid}), (s:Skill {canonical_name: 'Kubernetes'}) MERGE (c)-[:HAS_SKILL]->(s)", {"cid": cid})

    # Add experience mentioning Kubernetes
    query(
        """
        MATCH (c:Candidate {id: $cid})
        MERGE (e:Experience {id: 'corp-exp-1'})
        SET e.title = 'DevOps Lead', e.company = 'MegaCorp', e.start_date = '2021', e.end_date = '2023',
            e.description = 'Deployed microservices using Kubernetes on AWS'
        MERGE (c)-[:HAD]->(e)
        """,
        {"cid": cid},
    )

    # Add project with Python
    query(
        """
        MATCH (c:Candidate {id: $cid})
        MERGE (p:Project {name: 'PyCrawler', description: 'Web crawler in Python', commit_count: 10, url: 'http://gh/py'})
        MERGE (c)-[:BUILT]->(p)
        WITH p MATCH (s:Skill {canonical_name: 'Python'})
        MERGE (p)-[:USES]->(s)
        """,
        {"cid": cid},
    )

    # Run broadened evidence retrieval query
    res = evidence_for_skill_for_candidate(cid, ["Kubernetes", "Python"])
    assert res.result_set

    by_skill = {r[0]: (r[1], r[2]) for r in res.result_set}

    # Kubernetes: has experience evidence even without a project!
    k8s_projs, k8s_exps = by_skill["Kubernetes"]
    assert any(e.get("company") == "MegaCorp" for e in k8s_exps)

    # Python: has project evidence
    py_projs, py_exps = by_skill["Python"]
    assert any(p.get("name") == "PyCrawler" for p in py_projs)
