from career_graph.graph_writer import GraphWriter


def test_graph_writer_skill_normalization(tmp_path, monkeypatch):
    # point normalizer to our alias file in repo (default is already configured)
    gw = GraphWriter()

    parsed = {
        "name": "Proto User",
        "email": "proto@example.com",
        "skills": [
            {"canonical_name": "py", "aliases": ["py", "python3"], "confidence": 0.9}
        ],
        "projects": []
    }

    candidate = gw.write_parsed_candidate(parsed)
    # candidate should be created
    assert candidate.id

    # the skill linked to candidate should be canonicalized to "Python"
    session = gw
    # load via upsert to confirm idempotency and canonical name
    sk = gw.upsert_skill("py")
    assert sk.canonical_name == "Python"
