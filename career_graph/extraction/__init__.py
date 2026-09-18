"""Extraction module: structured extraction of skills/entities from raw inputs.

PRD Layer 2 uses Amazon Bedrock (Haiku) to extract structured data from
resumes, GitHub repos, and job descriptions. This module wraps Bedrock with a
deterministic heuristic fallback so the whole pipeline works locally without
AWS credentials.

Enable Bedrock with `CAREER_GRAPH_USE_BEDROCK=1` (plus AWS credentials).
Model ids are configurable via BEDROCK_*_MODEL env vars.
"""