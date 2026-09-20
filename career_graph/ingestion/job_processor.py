"""JobProcessor: shared consumer-side handler for one job posting.

This is the "JD Parser → Alias Normalizer → Graph Writer" stage of the PRD
pipeline. It is the single source of truth used by the SQS consumers, the API,
and the local `scripts/process_jobs.py` worker.

It accepts either:
  * a normalized scraper job  -> {"external_id", "source", "title", "company",
                                   "url", "location", "description"} or
  * a pre-parsed job          -> same + {"requirements":[{name, importance}]}

and writes the JobPosting + REQUIRES edges into the relational store, then
mirrors into FalkorDB (best-effort). Every skill passes through the alias
dictionary before any graph write.
"""
import logging
from typing import Dict, List, Optional

from ..extraction.bedrock import extract_job_skills
from ..graph_writer import GraphWriter
from ..normalizer.alias_normalizer import AliasNormalizer

log = logging.getLogger(__name__)


class JobProcessor:
    def __init__(self):
        self.gw = GraphWriter()
        self.normalizer = AliasNormalizer()

    def process(self, job: Dict) -> object:
        """Upsert the posting + REQUIRES edges; returns the JobPosting row."""
        title = (job.get("title") or "").strip()
        description = (job.get("description") or "").strip()
        company = job.get("company")

        # backward-compatible with old "raw text" messages via the heuristic parser
        if not title and description:
            from ..parsers.job_parser import JobParser

            parsed = JobParser().parse(description)
            title = parsed.get("title", "Job")
            company = company or parsed.get("company")

        if not title:
            raise ValueError("job missing title")

        extracted_data = {}
        requirements = job.get("requirements")
        if requirements is None:
            extracted_data = extract_job_skills(description, title)
            requirements = extracted_data.get("skills", [])

        location = job.get("location") or extracted_data.get("location")
        experience_level = job.get("experience_level") or extracted_data.get("experience_level")

        posting = self.gw.upsert_jobposting(
            title,
            company=company,
            description=description,
            source=job.get("source") or "scraper",
            url=job.get("url"),
            location=location,
            experience_level=experience_level
        )

        seen, requirements_out = set(), []
        for r in requirements:
            raw = r.get("name") or r.get("canonical_name") or ""
            canonical = self.normalizer.normalize(raw)
            key = canonical.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            importance = float(r.get("importance", 1.0))
            skill = self.gw.upsert_skill(canonical)
            self.gw.link_job_requirement(posting.id, skill.id, importance=importance)
            requirements_out.append({"name": canonical, "importance": importance})

        self._mirror(posting, job, requirements_out)
        return posting

    def _mirror(self, posting, job, requirements_out: List[Dict]):
        try:
            from ..falkor import career_graph
        except Exception:
            career_graph = None
        if career_graph is None:
            return
        from .falkor_mirror import mirror_job

        mirror_job(f"job:{posting.id}", posting.title, posting.company, job.get("url"), requirements_out)