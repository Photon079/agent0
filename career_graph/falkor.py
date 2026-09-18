import os
try:
    from falkordb import FalkorDB
except Exception:
    # Import may fail in environments without falkordb installed; raise a clear error at runtime
    FalkorDB = None

FALKOR_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKOR_PORT = int(os.getenv("FALKORDB_PORT", 6379))
FALKOR_PASSWORD = os.getenv("FALKORDB_PASSWORD", "HackathonSecret2026")


def _init_client():
    if FalkorDB is None:
        raise RuntimeError("falkordb-py is not installed in this environment")
    client = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT, password=FALKOR_PASSWORD)
    return client.select_graph("career_graph")


# singleton graph handle
_force_disable = os.getenv("CAREER_GRAPH_DISABLE_FALKOR", "").lower() in ("1", "true", "yes")
career_graph = None
if not _force_disable:
    try:
        career_graph = _init_client()
    except Exception:
        # lazy init; tests or static analysis can still import module
        career_graph = None


def query(cypher: str, params: dict | None = None):
    """Run a Cypher query against the selected FalkorDB graph.

    Returns the raw driver response. Caller should handle result parsing.
    """
    if career_graph is None:
        raise RuntimeError("FalkorDB client not initialized; ensure FALKORDB_HOST/PORT/PASSWORD and falkordb-py are available")
    return career_graph.query(cypher, params or {})