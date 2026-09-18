"""Script to run the FastAPI app via uvicorn (development)."""
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn


def main():
    uvicorn.run("career_graph.api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()