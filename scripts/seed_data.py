"""Seed the database with example data for development/demo."""
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.db import init_db, get_session
from career_graph import models, repository as repo


def seed():
    init_db(models.Base)

    # skills
    py = repo.create_skill("Python", aliases=["python3"])
    sql = repo.create_skill("SQL", aliases=["sql"])

    # candidate
    cand = repo.create_candidate("Alice Example", "alice@example.com")

    # link skills to candidate
    repo.link_candidate_skill(cand.id, py.id, confidence=0.9, evidence={"source": "resume"})

    # project
    with get_session() as session:
        project = models.Project(name="Demo Project", description="Example project using Python.", url="https://github.com/example/demo", commit_count=12, source="github")
        session.add(project)
        session.commit()
        session.refresh(project)
        # link project to python skill
        session.execute(models.project_skill.insert().values(project_id=project.id, skill_id=py.id, evidence={"files": ["main.py"]}))
        session.commit()

    # job posting
    with get_session() as session:
        job = models.JobPosting(title="Backend Engineer", company="Acme", description="Backend role requiring Python and SQL", source="fixture")
        session.add(job)
        session.commit()
        session.refresh(job)
        session.execute(models.job_requirement.insert().values(job_id=job.id, skill_id=py.id, importance=1.0))
        session.execute(models.job_requirement.insert().values(job_id=job.id, skill_id=sql.id, importance=0.8))
        session.commit()

    print("Seed complete.")


if __name__ == "__main__":
    seed()