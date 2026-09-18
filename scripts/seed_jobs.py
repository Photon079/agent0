"""Seed job fixtures into the local DB for testing/demo.

Reads `fixtures/jobs.json` if present and writes JobPosting nodes and required skills.
Note: fixtures/jobs.json uses the shape `{jobs: [{id, title, company, url, requirements: [{name, importance}]}]}`.
"""

import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
# Repo root goes on sys.path so the career_graph package is importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import os
from career_graph.db import init_db
from career_graph import models
from career_graph.graph_writer import GraphWriter


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "fixtures", "jobs.json")

    init_db(models.Base)

    if not os.path.exists(path):
        print("No fixtures/jobs.json found; create one to seed jobs.")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    gw = GraphWriter()
    for j in data.get("jobs", []):
        job = gw.upsert_jobposting(j.get("title"), company=j.get("company"), description=j.get("description"), source="fixture")
        for s in j.get("requirements", []):
            if isinstance(s, dict):
                name, importance = s.get("name"), s.get("importance", 1.0)
            else:
                name, importance = s, 1.0
            sk = gw.upsert_skill(name)
            gw.link_job_requirement(job.id, sk.id, importance=importance)

    print("Seeded jobs from fixtures/jobs.json")


if __name__ == "__main__":
    main()