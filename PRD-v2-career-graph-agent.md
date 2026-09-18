**Overall Rating for First Commit: 8.2 / 10**

### Detailed Breakdown

| Criterion                      | Score | Comment |
|-------------------------------|-------|-------|
| Real problem                  | 9.0   | Extremely real for students right now |
| Differentiation               | 8.5   | Knowledge graph + strict grounding is a clear step above “just another resume AI” |
| Technical depth (SE + AI)     | 8.5   | Graph + agents + Step Functions + Bedrock is strong signal |
| 4-day feasibility (4 people)  | 7.0   | Ambitious but doable if you stay disciplined on scope |
| Demo impact                   | 8.5   | The “show the graph evidence behind a bullet” moment is excellent |
| AWS usage quality             | 9.0   | Clean, purposeful use of many services |
| Amazon interview signal       | 8.5   | High — systems thinking + agents + real constraints |
| Startup / YC potential        | 7.5   | Solid early-career tools space, but crowded |
| Risk of looking generic       | Medium| Only if the grounding/evidence part is weak in the demo |

**Verdict:** This is one of the stronger student ideas for this specific hackathon. It hits the right balance of real pain, technical sophistication, and demo-ability. The biggest risks are (1) graph complexity slowing you down and (2) the generation step not being clearly “grounded” in the video.

---

# Detailed PRD for Building (Agent / Team Ready)

**Project Name:** Graph-Grounded Career Agent  
**Track:** Ship It  
**Timeline:** 72 hours  
**Team Size:** 4

### 1. Goal
Build a working system that:
1. Ingests a student’s resume + GitHub
2. Builds a living knowledge graph of verified skills and projects
3. Continuously pulls real job postings
4. Matches jobs via graph overlap
5. Generates a tailored, single-column LaTeX resume + cover letter where **every claim is grounded** in the graph
6. Surfaces skill gaps with micro-project suggestions

### 2. Non-Goals (Do Not Build)
- Actual auto-submission to ATS
- Cold email sending
- LinkedIn scraping
- Application tracking
- Full skill ontology (ESCO etc.)
- Multi-column resumes
- Complex auth beyond basic Cognito

---

### 3. System Layers (Bottom → Top)

#### Layer 1: Data Layer
**Purpose:** Durable storage of raw and processed data.

| Component | Technology | Details |
|---------|------------|-------|
| Object Storage | Amazon S3 | Resume PDFs, generated LaTeX/PDFs, job fixtures, alias dictionary |
| Graph Database | FalkorDB on ECS Fargate (public subnet) | Primary source of truth. Public IP + strong AUTH password. No VPC for Lambdas. |
| Relational / Metadata (optional) | DynamoDB | Job scrape metadata, user sessions, generation history |
| Queue | Amazon SQS | Decouple scraper from graph writer. Strip HTML before sending. |

**Key Collections / Buckets:**
- `resumes/{userId}/`
- `generated/{userId}/{jobId}/`
- `fixtures/jobs/`
- `config/skill-aliases.json`

#### Layer 2: Ingestion Layer
**Purpose:** Turn messy real-world inputs into clean graph nodes.

| Input | Pipeline | Output |
|------|----------|--------|
| Resume PDF | S3 → Textract → Bedrock Haiku (structured extraction) → Alias Normalizer → Graph Writer | Candidate, Skill, Experience, Project nodes |
| GitHub username | Lambda → GitHub API (repos, languages, README, commit stats) → Bedrock Haiku → Alias Normalizer → Graph Writer | Project nodes + USES edges + evidence |
| Job Postings | EventBridge → Scraper Lambda (Greenhouse/Lever/RemoteOK + S3 fixture fallback) → SQS → JD Parser (Haiku) → Alias Normalizer → Graph Writer | JobPosting + REQUIRES edges |

**Critical Rule:** Every skill string must pass through the alias dictionary before any graph write.

#### Layer 3: Knowledge Graph Layer
**Nodes:**
- `Candidate`
- `Skill` (canonical_name, aliases[], category)
- `Project` (name, description, url, commit_count, source)
- `Experience`
- `JobPosting`

**Edges:**
- `(Candidate)-[:HAS_SKILL {confidence, evidence}]->(Skill)`
- `(Candidate)-[:BUILT {role}]->(Project)`
- `(Project)-[:USES {evidence}]->(Skill)`
- `(JobPosting)-[:REQUIRES {importance}]->(Skill)`

**Core Queries (must be ready early):**
1. Ranked skill-overlap matching
2. Gap detection (skills required by job but missing from candidate)
3. Evidence retrieval (projects/commits that prove a skill)

#### Layer 4: Intelligence / Agent Layer
**Model Routing (strict):**

| Task | Model | Reason |
|------|-------|--------|
| Resume & GitHub extraction | Claude 3.5 Haiku | Speed + structured output |
| Job description parsing | Claude 3.5 Haiku | High volume |
| Grounded resume + cover letter generation | Claude 3.5 Sonnet | Better constraint following |

**Generation Rules (non-negotiable):**
- Only use information present in the retrieved subgraph
- Every bullet must follow X-Y-Z format where Z comes from real evidence
- Negative constraint in system prompt: “You may not mention any technology, library, metric, or project that does not appear in the provided graph context.”

#### Layer 5: Orchestration Layer
- **Step Functions** as the primary architecture artifact
- Orchestrates: Ingest → Extract → Normalize → Write Graph → Match → Generate
- Visible in the demo video

#### Layer 6: API & Frontend Layer
- **API Gateway** + Lambda
- **Frontend:** React on Amplify Hosting
- Key screens:
  1. Upload (resume + GitHub)
  2. Graph visualization (even simple)
  3. Ranked job matches
  4. Document preview (resume + cover letter)
  5. Gap + micro-project suggestion

#### Layer 7: Auth & Observability
- Cognito (basic email/password is enough)
- CloudWatch Logs + basic metrics

---

### 4. Tech Stack Summary

| Layer | Choice |
|-------|--------|
| Graph DB | FalkorDB (ECS Fargate, public subnet) |
| Compute | Lambda + Step Functions |
| AI | Amazon Bedrock (Haiku + Sonnet) |
| Storage | S3 + DynamoDB (optional) |
| Queue | SQS |
| Frontend | React + Amplify Hosting |
| Auth | Cognito |
| Resume Format | Single-column LaTeX (Jake’s Resume style) |
| Scraping | Custom Lambda + S3 fixtures fallback |

---

### 5. Team Split (Recommended)

| Person | Ownership |
|--------|-----------|
| **Graph Lead** | FalkorDB setup, schema, alias dictionary, Cypher queries, graph writer |
| **Agent Lead** | All Bedrock prompts, model routing, grounding constraints, LaTeX generation |
| **Frontend Lead** | Amplify app, upload flow, match list, document preview, graph viz |
| **Infra + Integration Lead** | Step Functions, scraper + fixtures, Textract, API Gateway, deploy, demo video |

---

### 6. Success Criteria (Must Hit)
- Real resume + real GitHub → real graph
- At least 15–20 real job postings in the graph (fixtures are fine)
- Matching returns sensible ranked results
- Generated resume has at least one bullet that can be visibly traced back to a project/commit in the demo
- Step Functions execution visible
- Public Amplify URL working

---

Would you like me to now expand any specific part in more detail (e.g. exact Cypher queries, Bedrock prompt templates, FalkorDB schema JSON, or the Friday critical path)?