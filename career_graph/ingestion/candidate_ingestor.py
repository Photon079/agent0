"""CandidateIngestor: shared handler for resume + GitHub ingestion.

PRD Layer 2: an ingress (S3/Textract for PDFs, GitHub API) is followed by
Bedrock extraction, alias normalization, and graph writes. This class is the
single source of truth for that middle section: it takes
  * resume plain text (or a local PDF via pypdf), or
  * a list of GitHub repo dicts (fetched by `github_fetcher`),
extracts structured data (Bedrock when enabled, heuristic otherwise), writes
the Candidate / Project / Skill nodes + edges to the relational store, and
mirrors into FalkorDB (best-effort).
"""
import logging
from typing import Any, Dict, List, Optional

from ..extraction.bedrock import extract_github_repos, extract_resume
from ..graph_writer import GraphWriter

log = logging.getLogger(__name__)


def pdf_to_text(path: str) -> str:
    """Extract text from a PDF locally (stand-in for AWS Textract)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(
            "PDF extraction requires `pypdf` (pip install pypdf). "
            "In production this step is AWS Textract."
        )
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


class CandidateIngestor:
    def __init__(self):
        self.gw = GraphWriter()

    def ingest_resume_text(self, text: str, source: str = "resume") -> Any:
        parsed = extract_resume(text)
        candidate = self.gw.write_parsed_candidate(parsed)
        self._mirror_candidate(candidate, parsed)
        return candidate

    def ingest_resume_pdf(self, path: str) -> Any:
        return self.ingest_resume_text(pdf_to_text(path), source="resume-pdf")

    def ingest_github_repos(self, repos: List[Dict[str, Any]], name: Optional[str] = None, email: Optional[str] = None) -> Any:
        parsed = extract_github_repos(repos)
        parsed["name"] = name or parsed.get("name") or ""
        parsed["email"] = email or parsed.get("email")
        candidate = self.gw.write_parsed_candidate(parsed)
        self._mirror_candidate(candidate, parsed)
        return candidate

    def ingest_github_username(self, username: str, token: Optional[str] = None, max_repos: int = 10, name: Optional[str] = None, email: Optional[str] = None) -> Any:
        from .github_fetcher import fetch_github_repos

        try:
            repos = fetch_github_repos(username, token=token, max_repos=max_repos)
        except Exception as e:
            raise RuntimeError(
                f"GitHub fetch failed for '{username}'. Check the username / GITHUB_TOKEN "
                f"(rate limits are 60 req/hr unauthenticated): {type(e).__name__}: {e}"
            ) from e
        if not repos:
            raise RuntimeError(f"No public repositories found for '{username}'")
        return self.ingest_github_repos(repos, name=name or username, email=email)

    def _mirror_candidate(self, candidate, parsed: Dict):
        try:
            from ..falkor import career_graph
        except Exception:
            career_graph = None
        if career_graph is None:
            return
        from .falkor_mirror import mirror_candidate

        mirror_candidate(
            f"cand:{candidate.id}",
            candidate.name,
            parsed.get("skills", []),
            parsed.get("projects", []),
            experiences=parsed.get("experiences", []),
        )