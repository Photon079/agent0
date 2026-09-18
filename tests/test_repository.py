from career_graph.db import init_db, get_session
from career_graph import models
from career_graph import repository as repo
from career_graph.models import JobPosting, job_requirement


def test_create_and_match():
    init_db(models.Base)

    py = repo.create_skill("Python", aliases=["python3"])
    sql = repo.create_skill("SQL")
    cand = repo.create_candidate("Bob Tester", "bob@test.com")
    repo.link_candidate_skill(cand.id, py.id, confidence=0.8)

    with get_session() as session:
        job = JobPosting(title="Test Job", company="Acme", description="Test role")
        session.add(job)
        session.commit()
        session.refresh(job)
        session.execute(job_requirement.insert().values(job_id=job.id, skill_id=py.id, importance=1.0))
        session.execute(job_requirement.insert().values(job_id=job.id, skill_id=sql.id, importance=0.5))
        session.commit()

    matches = repo.match_jobs_by_skill_overlap(cand.id)
    assert matches, "Expected at least one matching job"
    # highest overlap should be >=1
    assert matches[0][1] >= 1
