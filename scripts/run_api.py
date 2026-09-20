"""Script to run the FastAPI app via uvicorn (development)."""
import os
import sys

# Allow running directly: python scripts/<name>.py from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn


def _load_env(env_path: str) -> None:
    """Load KEY=VALUE pairs from an env file into os.environ (stdlib only)."""
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Don't overwrite variables already set in the shell environment
            if key and key not in os.environ:
                os.environ[key] = value


def main():
    # Load secrets from aws_live.env before uvicorn starts
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aws_live.env"))
    _load_env(env_file)

    uvicorn.run("career_graph.api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()