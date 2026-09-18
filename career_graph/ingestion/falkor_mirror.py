"""Optional mirroring of relational writes into the FalkorDB graph.

Both SQS consumers call these helpers so that FalkorDB gets populated even
during local development. The payloads are plain JSON-able dicts (never ORM
objects) to avoid detached-instance issues. They are best-effort: any
FalkorDB failure is logged and swallowed so the relational write still
succeeds.
"""
import json
import logging

from ..falkor import career_graph

log = logging.getLogger(__name__)


def _primitive(value):
    """FalkorDB property values must be primitives (or arrays of primitives).

    Dict evidence (e.g. {"snippet": ...}) must be serialized first.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def mirror_candidate(candidate_id, name, skills, projects):
    """Mirror a candidate + skills/projects into FalkorDB.

    candidate_id: string id (e.g. "cand:123")
    skills:       [{name, confidence, evidence}]
    projects:     [{name, description, url, commit_count, source, skills_used}]
    """
    if career_graph is None:
        return
    from ..normalizer.alias_normalizer import AliasNormalizer
    from ..graph_writer_falkor import write_candidate_graph

    try:
        an = AliasNormalizer()
        write_candidate_graph(
            {
                "candidate": {"id": candidate_id, "name": name, "resume_url": None},
                "skills": [{"name": s.get("name") or s.get("canonical_name"), "confidence": s.get("confidence", 1.0), "evidence": _primitive(s.get("evidence"))} for s in skills],
                "projects": [
                    {
                        "name": p.get("name"),
                        "description": p.get("description", ""),
                        "url": p.get("url", ""),
                        "commit_count": p.get("commit_count", 0),
                        "source": p.get("source", "relational"),
                        "skills_used": p.get("skills_used") or p.get("skills") or [],
                    }
                    for p in projects
                ],
            },
            an,
        )
    except Exception:
        log.exception("FalkorDB candidate mirror failed")


def mirror_job(job_id, title, company, url, requirements):
    """Mirror a JobPosting + REQUIRES edges into FalkorDB.

    requirements: [{name, importance}]
    """
    if career_graph is None:
        return
    from ..normalizer.alias_normalizer import AliasNormalizer
    from ..graph_writer_falkor import write_job_posting

    try:
        an = AliasNormalizer()
        write_job_posting(
            {"id": job_id, "title": title, "company": company, "url": url, "requirements": requirements},
            an,
        )
    except Exception:
        log.exception("FalkorDB job mirror failed")