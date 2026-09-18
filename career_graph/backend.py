"""Active backend resolution for Career Graph queries.

Determines whether query endpoints (/match, /gap, /evidence) execute
against FalkorDB (OpenCypher) or SQLite (SQLAlchemy).
"""
import logging
import os
from typing import Literal

log = logging.getLogger(__name__)


def is_falkor_available() -> bool:
    """Check if FalkorDB is reachable and responding."""
    try:
        from .falkor import query, career_graph

        if career_graph is None:
            return False
        # Lightweight ping query
        query("RETURN 1 as ok")
        return True
    except Exception as e:
        log.debug("FalkorDB ping failed: %s", e)
        return False


def get_active_backend() -> Literal["falkor", "sqlite"]:
    """Select active query backend based on CAREER_GRAPH_BACKEND and service health.

    Rules:
    - CAREER_GRAPH_BACKEND=sqlite: force SQLite.
    - CAREER_GRAPH_BACKEND=falkor: use FalkorDB if reachable, else fall back to SQLite.
    - Default (unset or empty): default to 'falkor' when FalkorDB is active (falkor-run),
      falling back to SQLite if the connection is unavailable or times out.
    """
    configured = os.getenv("CAREER_GRAPH_BACKEND", "").lower().strip()
    if configured == "sqlite":
        return "sqlite"

    if is_falkor_available():
        return "falkor"

    if configured == "falkor":
        log.warning(
            "CAREER_GRAPH_BACKEND=falkor was requested, but FalkorDB is not reachable. "
            "Falling back to SQLite."
        )
    return "sqlite"


__all__ = ["is_falkor_available", "get_active_backend"]
