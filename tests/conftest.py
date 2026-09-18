import os
import sys
import tempfile

# Ensure the repo root (with the `career_graph` package) is on sys.path.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Use an isolated temp DB for every test session so runs never collide with
# the on-disk career_graph.db (unique constraint on skills.canonical_name).
# Must be set before any `career_graph.db` import.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + _tmp.name
_tmp.close()

# Tests must not write to the live FalkorDB graph.
os.environ.setdefault("CAREER_GRAPH_DISABLE_FALKOR", "1")

import pytest  # noqa: E402
from career_graph.db import engine  # noqa: E402
from career_graph import models  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_db():
    """Fresh, empty schema for every test to keep tests independent."""
    models.Base.metadata.drop_all(engine)
    models.Base.metadata.create_all(engine)
    yield