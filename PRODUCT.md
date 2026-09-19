# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Any technical job seeker — students, early-career developers, bootcamp grads, career changers — who has a resume and/or a GitHub profile and wants to understand where they stand in the job market. The user's situation: they know they have skills but can't see how their profile maps onto real job requirements, which postings are the best fit, or where the gaps are.

## Product Purpose

CareerGraph ingests a user's resume and GitHub profile, builds a knowledge graph of verified skills, projects, and experience, pulls real job postings from multiple sources, matches jobs by skill overlap, and surfaces skill gaps — all grounded in traceable evidence. Success means a job seeker can see exactly which roles fit their verified skills, what's missing for target roles, and have proof behind every skill claim.

## Positioning

Two differentiators working together:

1. **Evidence-grounded claims.** Every skill in the graph traces back to real proof — GitHub commits, project authorship, work experience records. Nothing is hallucinated or self-reported without evidence.
2. **Knowledge-graph matching.** Job matching uses graph overlap (shared skills between the candidate's verified graph and a job's required skills graph), not keyword proximity. Gap analysis is structural, not heuristical.

The combination means a candidate's match to a job is explainable and auditable, not a black-box relevance score.

## Operating Context

Self-service tool: the job seeker connects their own GitHub, pastes their own resume, and explores matches and gaps directly. No intermediary operator.

Workflows:
- **Ingest:** Connect GitHub username (fetches all public repos, extracts languages and commit counts) or paste resume text. Optionally paste job descriptions manually.
- **Explore:** Dashboard shows candidates, jobs, and unique skills at a glance. Candidate detail view shows per-skill evidence (projects with commit counts, experience with roles/durations).
- **Match:** View ranked job matches by skill overlap for any candidate.
- **Gap analysis:** Select a specific job posting and see exactly which required skills the candidate is missing.
- **Job refresh:** Scrape live job postings from Greenhouse, Lever, RemoteOK, and Arbeitnow boards.

## Capabilities and Constraints

**Built:**
- Resume parsing (heuristic + optional Bedrock/Claude extraction)
- GitHub profile ingestion (all public repos, languages, commit stats)
- Job scraping from four boards (Greenhouse, Lever, RemoteOK, Arbeitnow) with fixture fallback
- Alias-based skill normalization (canonical skill dictionary)
- Relational graph (SQLite/SQLAlchemy) — default, zero-setup
- FalkorDB graph backend (Docker) — secondary
- FastAPI backend with full REST API
- React + Vite frontend (dashboard, candidates, jobs, ingest, candidate detail with evidence + matching + gap analysis)

**Not built (per PRD):**
- Grounded resume/cover-letter generation ("intelligence layer")
- AWS Step Functions orchestration
- Cognito auth / user accounts
- AWS Textract PDF extraction
- CloudFormation infrastructure

**Stack:** Python (FastAPI, SQLAlchemy, Alembic) backend; React 18 + Vite + React Router 7 frontend; SQLite (default) or FalkorDB (Docker) storage.

## Brand Commitments

Name and visual identity are flexible — "CareerGraph" and the hexagon (⬡) logo are working names, not locked commitments.

## Evidence on Hand

- Real job fixtures (`fixtures/jobs.json`) with actual job postings
- Sample resume (`fixtures/resume_sample.txt`)
- Scraped job data from live boards (`fixtures/scraped/`)
- Working API with all endpoints functional
- No testimonials, case studies, or external validation exist. Future work must not fabricate these.

## Product Principles

1. **Every claim has a receipt.** No skill appears in the graph without traceable evidence — a commit, a project, an experience record. The system will not fabricate or inflate.
2. **The graph is the product.** Matching, gap analysis, and future generation all derive from the same knowledge graph. There is one source of truth, not parallel heuristics.
3. **Self-service over gatekeepers.** The job seeker controls their own data and sees their own results. No recruiter intermediary is required.
4. **Real data, real jobs.** Job postings come from live boards with fixture fallback. The system operates on actual market data, not toy examples.
5. **Ship working, then polish.** Hackathon origin, real-product ambition. Build features that work end-to-end before optimizing any one layer.
