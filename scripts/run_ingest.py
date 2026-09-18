"""Run the ingestion service once (process all files in fixtures/inbox)."""
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.ingestion.service import IngestionService


def main():
    svc = IngestionService(inbox_dir="fixtures/inbox")
    svc.process_once()


if __name__ == "__main__":
    main()