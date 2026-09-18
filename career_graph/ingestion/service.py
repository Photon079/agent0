"""Ingestion service that reads fixtures (local JSON/text) and routes
them through parsers into the graph via GraphWriter.

This is a minimal local implementation: it watches a folder for files and
processes them once. Production would replace this with SQS/S3/Lambda triggers.
"""
import json
import os
from typing import Callable

from ..graph_writer import GraphWriter
from ..parsers.simple_resume_parser import SimpleResumeParser
from ..parsers.github_parser import GithubParser
from ..parsers.job_parser import JobParser


class IngestionService:
    def __init__(self, inbox_dir: str = "fixtures/inbox"):
        self.inbox_dir = inbox_dir
        self.gw = GraphWriter()
        self.parsers = {
            "resume": SimpleResumeParser(),
            "github": GithubParser(),
            "job": JobParser(),
        }

    def process_once(self):
        if not os.path.exists(self.inbox_dir):
            print("Inbox not found:", self.inbox_dir)
            return

        for fname in os.listdir(self.inbox_dir):
            path = os.path.join(self.inbox_dir, fname)
            if not os.path.isfile(path):
                continue

            with open(path, "r", encoding="utf-8") as f:
                try:
                    payload = json.load(f)
                except Exception:
                    # fallback to raw text job parsing
                    text = open(path, "r", encoding="utf-8").read()
                    parsed = self.parsers["job"].parse(text)
                    job = self.gw.upsert_jobposting(parsed["title"], parsed.get("company"), parsed.get("description"), source="fixture")
                    for s in parsed.get("skills", []):
                        sk = self.gw.upsert_skill(s.get("canonical_name"))
                        self.gw.link_job_requirement(job.id, sk.id, importance=s.get("importance", 1.0))
                    os.remove(path)
                    continue

            # payload must include a 'type' key: resume, github, job
            t = payload.get("type")
            if t == "resume":
                parsed = self.parsers["resume"].parse(payload.get("text", ""))
                # associate parsed candidate with optional owner
                cand = self.gw.write_parsed_candidate(parsed)
                print("Wrote candidate", cand.id)

            elif t == "github":
                parsed = self.parsers["github"].parse(payload.get("repos", []))
                # write projects (candidate association optional)
                cand_email = payload.get("email")
                candidate = None
                if cand_email:
                    candidate = self.gw.upsert_candidate(payload.get("name", ""), cand_email)
                for p in parsed.get("projects", []):
                    proj = self.gw.upsert_project(p.get("name"), description=p.get("description"), url=p.get("url"), commit_count=p.get("commit_count", 0), source="github", candidate_id=(candidate.id if candidate else None))
                    for sk_name in p.get("skills", []):
                        if sk_name:
                            sk = self.gw.upsert_skill(sk_name)
                            self.gw.link_project_skill(proj.id, sk.id)

            elif t == "job":
                parsed = self.parsers["job"].parse(payload.get("text", ""))
                job = self.gw.upsert_jobposting(parsed.get("title"), parsed.get("company"), parsed.get("description"), source="fixture")
                for s in parsed.get("skills", []):
                    sk = self.gw.upsert_skill(s.get("canonical_name"))
                    self.gw.link_job_requirement(job.id, sk.id, importance=s.get("importance", 1.0))

            else:
                print("Unknown payload type, skipping:", t)

            # remove processed file
            try:
                os.remove(path)
            except Exception:
                pass


__all__ = ["IngestionService"]