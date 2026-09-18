"""Ingest a candidate (resume and/or GitHub) into the graph (relational + FalkorDB).

Resume path: accepts .txt or .pdf (local pypdf; Textract in production).
GitHub path: fetches repos via the GitHub API, extracts skills, writes
Candidate/Project/Skill nodes + HAS_SKILL/BUILT/USES edges.

Examples:
    python scripts/ingest_candidate.py --resume path/to/resume.pdf
    python scripts/ingest_candidate.py --github someusername --github-token $GITHUB_TOKEN
    python scripts/ingest_candidate.py --resume r.txt --github someusername
"""
import argparse
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.ingestion.candidate_ingestor import CandidateIngestor, pdf_to_text


def main():
    parser = argparse.ArgumentParser(description="Ingest a candidate resume and/or GitHub profile.")
    parser.add_argument("--resume", help="Path to resume (.txt or .pdf)")
    parser.add_argument("--github", help="GitHub username to fetch repos from")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub API token (or $GITHUB_TOKEN)")
    parser.add_argument("--max-repos", type=int, default=10)
    args = parser.parse_args()

    if not args.resume and not args.github:
        parser.error("provide --resume and/or --github")

    ingestor = CandidateIngestor()

    if args.resume:
        if args.resume.lower().endswith(".pdf"):
            text = pdf_to_text(args.resume)
        else:
            with open(args.resume, "r", encoding="utf-8") as f:
                text = f.read()
        cand = ingestor.ingest_resume_text(text)
        print(f"Resume -> candidate id={cand.id} name={cand.name}")

    if args.github:
        cand = ingestor.ingest_github_username(args.github, token=args.github_token, max_repos=args.max_repos)
        print(f"GitHub -> candidate id={cand.id} name={cand.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())