# Graph-Grounded Career Agent

Graph-grounded career agent: ingests a resume + GitHub, builds a knowledge graph of
skills/projects, pulls job postings, matches jobs by skill overlap, and surfaces gaps.
Two graph backends are supported:

1. **Relational (SQLite + SQLAlchemy)** — default, zero-setup, fully tested.
2. **FalkorDB (graph DB)** — runs in Docker; the PRD's "primary source of truth" target.

## Layout

```
career_graph/
  models.py               # SQLAlchemy nodes: Candidate/Skill/Project/Experience/JobPosting + edges
  db.py                   # SQLAlchemy engine/session (DATABASE_URL env)
  graph_writer.py         # relational GraphWriter (upserts nodes/edges)
  repository.py           # relational queries: overlap match, gap detection, evidence
  falkor.py               # FalkorDB client + query()
  graph_writer_falkor.py  # writes Candidate/Project/Skill/JobPosting into FalkorDB
  repository_cypher.py    # Cypher: overlap match, gap detection, evidence
  api/app.py              # FastAPI: /parse/resume, /parse/github, /parse/job, /match, /gap, /evidence
  normalizer/             # alias-based skill canonicalization (skill-aliases.json)
  parsers/                # heuristic resume/github/job parsers + JSON schema validator
  extraction/             # Bedrock (Claude Haiku) structured extraction + heuristic fallback
  scraper/                # job scraper: Greenhouse/Lever/RemoteOK/Arbeitnow + fixtures,
                          # HTML stripping, SQS producer, EventBridge lambda handler
  ingestion/              # SQS consumers (full + minimal), JobProcessor, CandidateIngestor,
                          # GitHub API fetcher, S3/SQS adapters, FalkorDB mirroring helper
scripts/
  create_db.py, seed_data.py, seed_jobs.py
  run_api.py              # uvicorn career_graph.api.app:app
  run_scraper.py          # scrape job postings -> SQS or fixtures/scraped/jobs.json
  process_jobs.py         # parse + write scraped jobs into the graph (relational + FalkorDB)
  ingest_candidate.py     # ingest resume (.txt/.pdf) and/or GitHub username into the graph
  run_sqs_consumer.py     # full consumer (DLQ, backoff, Prometheus, threads)
  run_sqs_consumer_minimal.py
  run_ingest.py           # process files in fixtures/inbox
  run_falkordb.sh         # start FalkorDB Docker container
  falkor_verification.py  # end-to-end FalkorDB checklist (PRD Friday path)
alembic/                  # SQLAlchemy migrations
fixtures/jobs.json        # seed job postings
fixtures/scraped/         # local scrape output (S3 bucket stand-in)
fixtures/resume_sample.txt
tests/                    # pytest suite (relational + SQS/moto + schema + scraper + ingestion)
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make seed         # create DB + seed candidate/job
make runserver    # FastAPI on :8000
```

Useful endpoints:

- `POST /parse/resume` (form `text` or file) → `candidate_id`
- `POST /parse/github` (JSON `{repos, name, email}`) → projects
- `POST /parse/job` (form `text` or file) → `job_id`
- `GET  /match/{candidate_id}` → ranked jobs by skill overlap
- `GET  /gap/{candidate_id}/{job_id}` → missing skills
- `GET  /evidence/skill/{skill_id}` → evidence for a skill

## SQS consumer

Poll a queue; messages are JSON with a `type` of `resume`, `github`, or `job`.
The `job` message body is the normalized scraper output (`{"type":"job","job":{...}}`).

```bash
SQS_QUEUE_URL=<queue-url> make runconsumer        # full consumer (DLQ/metrics/backoff)
SQS_QUEUE_URL=<queue-url> make runconsumerminimal # single-threaded prototype
```

Set `SQS_DLQ_URL` (+ `SQS_DLQ_THRESHOLD`, default 5) and `METRICS_PORT` for the extras.

## Scraper (EventBridge → Scraper → SQS → graph)

Package: `career_graph/scraper/`. Fetches job postings from Greenhouse, Lever,
RemoteOK, and Arbeitnow, strips HTML, and normalizes to one shape. Any source
failure falls back to fixtures (PRD rule); sources are capped per run.

```bash
# live scrape (needs a Greenhouse board token + Lever company slug)
GREENHOUSE_BOARD_TOKEN=stripe LEVER_COMPANY=leverdemo make scrape \
    SCRAPE_SOURCES="greenhouse lever remoteok arbeitnow" SCRAPE_LIMIT=3

# then parse skills + write POSTING/REQUIRES into relational + FalkorDB
make process    # or: python scripts/process_jobs.py --file fixtures/scraped/jobs.json

# with a queue, scrape sends directly to SQS and the consumer picks it up
SQS_QUEUE_URL=<queue-url> python scripts/run_scraper.py --sources greenhouse lever --limit 5
```

`career_graph/scraper/lambda_handler.py` is the EventBridge-triggered Lambda
entry point (`{ "limit_per_source": 10, "sources": [...] }`); without
`SQS_QUEUE_URL` it persists the scrape to `/tmp` for a local worker.

## Candidate ingestion (resume + GitHub)

Package: `career_graph/ingestion/` — `CandidateIngestor` is the shared handler
used by the SQS consumers, scripts, and API. Skill tags go through the alias
dictionary; writes land in the relational store and mirror to FalkorDB.

```bash
make ingest RESUME=fixtures/resume_sample.txt        # text or PDF (pypdf stand-in for Textract)
make ingest GITHUB_USERNAME=kelseyhightower          # GitHub API -> projects + skills
make ingest RESUME=fixtures/resume_sample.txt GITHUB_USERNAME=kelseyhightower
```

## Bedrock extraction

Extraction is Bedrock-first when enabled, and falls back to deterministic
heuristics otherwise (so the whole pipeline runs without AWS).

```bash
CAREER_GRAPH_USE_BEDROCK=1 python scripts/process_jobs.py --file fixtures/scraped/jobs.json
```

Model ids are configurable via `BEDROCK_RESUME_MODEL`, `BEDROCK_JD_MODEL`,
`BEDROCK_GITHUB_MODEL`; debug fallback reasons with `BEDROCK_DEBUG=1`.

## FalkorDB

```bash
make falkor-run     # docker run falkordb/falkordb (port 6379, password HackathonSecret2026)
make falkor-verify  # init indexes, normalization check, inject fixtures, run match/gap queries
```

Ingestion consumers mirror writes into FalkorDB automatically when the container is up
(best-effort; the relational store remains the source of truth locally).

## Tests

```bash
make test    # or: pytest -q
```

## What is NOT built (vs PRD)

The PRD also calls for grounded resume/cover-letter generation (“intelligence
layer”), the Step Functions orchestration + EventBridge deploy config,
a React/Amplify frontend with Cognito auth, and AWS Textract/CloudFormation
infrastructure. Those are still open; scraper + ingestion (local) and the graph +
matching layers are complete.