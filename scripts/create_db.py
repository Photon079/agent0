"""Utility script to create the database tables."""
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from career_graph.db import init_db
from career_graph import models


def main():
    init_db(models.Base)
    print("Database tables created.")


if __name__ == "__main__":
    main()