"""Verification checklist runner for local FalkorDB per PRD Friday checklist.

Run from the repo root:
    python scripts/falkor_verification.py
"""

import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
# Repo root goes on sys.path so the career_graph package is importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import os
from pathlib import Path

from career_graph.falkor import query, career_graph
from career_graph.normalizer.alias_normalizer import AliasNormalizer
from career_graph.graph_writer_falkor import create_performance_indexes, write_job_posting


def rows(res):
    rs = getattr(res, "result_set", None)
    return rs or []


def check_container():
    try:
        # simple ping using an empty query (depends on falkordb client behaviour)
        query("RETURN 1 as ok")
        print("FalkorDB: reachable and responding")
    except Exception as e:
        raise RuntimeError("FalkorDB not reachable: %s" % e)


def normalization_check():
    sn = AliasNormalizer()
    variants = ["postgres", "PostgreSQL", "Postgres DB"]
    canon = [sn.normalize(v) for v in variants]
    print("Normalized variants:", list(zip(variants, canon)))

    # write the three as skills to the graph and validate only one canonical node exists
    for v in set(canon):
        query("MERGE (s:Skill {canonical_name: $name}) RETURN s", {"name": v})

    res = query("MATCH (s:Skill {canonical_name: $name}) RETURN count(s) as cnt", {"name": canon[0]})
    print("count for canonical skill node:", res.result_set)


def inject_fixtures(limit: int = 5):
    fixtures_path = Path(__file__).resolve().parent.parent / "fixtures" / "jobs.json"
    if not fixtures_path.exists():
        print("fixtures/jobs.json not found; skipping fixture injection")
        return
    data = json.loads(fixtures_path.read_text())
    jobs = data.get("jobs", [])[:limit]
    sn = AliasNormalizer()
    for j in jobs:
        # adapt to job shape expected by graph writer
        job_payload = {
            "id": j.get("id") or j.get("url"),
            "title": j.get("title"),
            "company": j.get("company"),
            "url": j.get("url"),
            "requirements": [{"name": r.get("name", r), "importance": r.get("importance", 1.0)} if isinstance(r, dict) else {"name": r, "importance": 1.0} for r in j.get("requirements", [])]
        }
        write_job_posting(job_payload, sn)
    print(f"Injected {len(jobs)} fixtures into FalkorDB")


def run_queries(candidate_id: str, job_id: str):
    # run the core queries via Cypher
    print("Running overlap query...")
    overlap_q = """
    MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(s:Skill)<-[r:REQUIRES]-(j:JobPosting)
    RETURN j.id AS job_id, count(s) AS overlap_score, collect(s.canonical_name) AS matched_skills
    ORDER BY overlap_score DESC
    LIMIT 10
    """
    res1 = query(overlap_q, {"candidate_id": candidate_id})
    print("overlap result:", res1.result_set)

    print("Running gap detection...")
    gap_q = """
    MATCH (j:JobPosting {id: $job_id})-[r:REQUIRES]->(s:Skill)
    OPTIONAL MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(s)
    WITH s, r, c
    WHERE c IS NULL
    RETURN s.canonical_name AS missing_skill, r.importance AS importance, s.category AS category
    """
    res2 = query(gap_q, {"candidate_id": candidate_id, "job_id": job_id})
    print("gap result:", res2.result_set)

    print("Running broadened evidence retrieval (projects + corporate experience)...")
    from career_graph.repository_cypher import evidence_for_skill_for_candidate
    res3 = evidence_for_skill_for_candidate(candidate_id, ["PostgreSQL", "Python"])
    print("evidence result:", res3.result_set)


if __name__ == "__main__":
    create_performance_indexes()
    check_container()
    normalization_check()
    inject_fixtures()
    # these ids should be replaced with real test ids from fixtures
    run_queries(candidate_id="test-cand-001", job_id="test-job-001")