from career_graph.parsers.schema_validator import validate_extraction


def test_validate_good_payload():
    payload = {
        "candidate": {"id": "cand_1", "name": "Jane Doe", "resume_url": "s3://..."},
        "skills": [{"name": "Postgres DB", "confidence": 0.9, "evidence": "Resume"}],
        "projects": [{"name": "Job Engine", "description": "...", "url": "https://...", "commit_count": 10, "skills_used": ["Python"]}],
    }
    ok, errs = validate_extraction(payload)
    assert ok
    assert errs == []


def test_validate_missing_candidate():
    payload = {"skills": [{"name": "Postgres DB"}]}
    ok, errs = validate_extraction(payload)
    assert not ok
    assert errs