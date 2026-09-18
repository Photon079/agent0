from career_graph.db import init_db
from career_graph import models
from career_graph.graph_writer import GraphWriter
from career_graph.db import get_session
from career_graph.models import Candidate, Skill, Project
from sqlalchemy import select


def test_graph_writer_creates_nodes_and_edges():
    init_db(models.Base)
    gw = GraphWriter()

    parsed = {
        "name": "Tester",
        "email": "tester@example.com",
        "skills": [{"canonical_name": "Python", "confidence": 0.9}],
        "projects": [{"name": "TestProj", "description": "desc", "url": "https://example.com/testproj", "commit_count": 3, "skills": ["Python"]}]
    }

    cand = gw.write_parsed_candidate(parsed)

    with get_session() as session:
        db_cand = session.get(Candidate, cand.id)
        assert db_cand is not None
        assert db_cand.email == "tester@example.com"

        # skill exists
        skills = session.scalars(select(Skill).where(Skill.canonical_name == "Python")).all()
        assert skills

        # project exists and linked
        proj = session.scalars(select(Project).where(Project.url == "https://example.com/testproj")).first()
        assert proj is not None
