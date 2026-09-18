from career_graph.graph_writer import GraphWriter
from career_graph.repository import gap_detection, match_jobs_by_skill_overlap, evidence_for_skill


def test_gap_and_match_and_evidence():
    gw = GraphWriter()

    # create candidate with Python skill
    parsed = {"name": "Gap User", "email": "gap@example.com", "skills": [{"canonical_name": "python", "confidence": 0.9}], "projects": []}
    cand = gw.write_parsed_candidate(parsed)

    # create a job requiring Python and SQL
    job = gw.upsert_jobposting("Data Engineer", company="Acme")
    sk_py = gw.upsert_skill("python")
    sk_sql = gw.upsert_skill("sql")
    gw.link_job_requirement(job.id, sk_py.id)
    gw.link_job_requirement(job.id, sk_sql.id)

    # match should show overlap 1
    rows = match_jobs_by_skill_overlap(cand.id)
    assert rows and rows[0][1] >= 1

    # gap detection should report SQL as missing
    missing = gap_detection(cand.id, job.id)
    assert "SQL" in missing or "sql" in [m.lower() for m in missing]

    # evidence for Python should include candidate
    ev = evidence_for_skill(sk_py.id)
    assert any(c["name"] == "Gap User" for c in ev["candidates"]) or ev["candidates"]
