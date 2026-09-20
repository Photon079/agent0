# Agent0: Graph-Grounded Career Intelligence

Agent0 is a next-generation career intelligence platform. It ingests a candidate's resume and GitHub profile, builds a powerful knowledge graph of their skills and projects, pulls active job postings, intelligently matches them by skill overlap and experience tier, and surfaces actionable skill gaps. 

It features an interactive **React/Vite Frontend** and a **FastAPI Intelligence Layer** capable of dynamically generating Proof-Backed LaTeX/PDF Resumes customized to specific job descriptions.

## Complete Feature Set (Production Ready)

1. **Unified Candidate Ingestion**
   - Ingests both a PDF Resume and a GitHub username in a single flow.
   - Extracts a rich array of modern frameworks, soft skills, and primary languages.
2. **Job Scraping & Matching**
   - Built-in job scraper hits Greenhouse, Lever, RemoteOK, and Arbeitnow.
   - Multiplicative ranking algorithm matches candidates to jobs while heavily penalizing experience mismatches (e.g., preventing Junior candidates from matching Senior roles).
3. **Intelligence Layer: Gap Analysis & Micro-Projects**
   - Identifies exact missing skills for a job.
   - Uses AWS Bedrock (Claude) to generate actionable, step-by-step micro-projects with direct links to learning resources (like freeCodeCamp) to bridge the gap.
4. **Agentic Resume Generation**
   - Programmatically drafts a customized, LaTeX-based `.pdf` resume proving the candidate's exact fit for a specific role based on their graph evidence.
5. **Docker Deployment Architecture**
   - Pre-configured `Dockerfile` and `docker-compose.yml` for instantaneous deployment on AWS EC2 or any Linux host.

---

## 🚀 Quick Start (Local Development)

### Backend (Python/FastAPI)
```bash
# 1. Setup virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Seed the database with mock jobs
make seed

# 3. Run the API (Listening on http://localhost:8000)
make runserver
```

### Frontend (React/Vite)
Open a separate terminal window:
```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start the Vite dev server
npm run dev
```

> [!IMPORTANT]
> **Camera / Webcam Permissions:** The new Agent0 UI features a highly dynamic, interactive webcam-based particle effect. When you open the frontend (`http://localhost:5173`), your browser will ask for Camera permissions. **You must "Allow" this permission** for the visual effects to initialize correctly!

---

## 🐳 Quick Start (AWS / Docker Deployment)

If you are deploying this to an AWS EC2 instance, you do not need to install Python or Node locally. The entire application (Frontend, Backend, and the LaTeX PDF compiler) is packaged in Docker.

```bash
# 1. Clone the repository on your EC2 Ubuntu instance
git clone <your-repo-url>
cd agent0

# 2. Start the entire platform
sudo docker-compose up -d --build
```
- The **Frontend** will be available on Port `80` (Standard HTTP).
- The **Backend API** will run on Port `8000`.
- All SQLite databases and generated PDFs are stored in shared volumes so no data is lost on restart.

---

## Architecture

```text
frontend/                 # Modern React/Vite UI (Agent0 Dashboard & Graph View)
career_graph/
  api/app.py              # FastAPI endpoints (/ingest/unified, /match, /scrape/jobs, /tailor-resume)
  extraction/bedrock.py   # Claude AI integration for Micro-projects
  parsers/                # Heuristic keyword parsers (GitHub & Resumes)
  resume/                 # Pipeline for LaTeX/PDF Resume Generation
  repository.py           # Core SQL Relational matching & gap detection
scripts/                  # Database seed scripts
docker-compose.yml        # AWS Deployment orchestration
```

### Notes on Graph Backends
By default, the platform uses a **Relational (SQLite)** approach for maximum portability and zero-setup local development. 
The codebase also includes full support for **FalkorDB** (a dedicated Graph database). You can spin it up via `make falkor-run` if you prefer true graph-native cypher queries.
