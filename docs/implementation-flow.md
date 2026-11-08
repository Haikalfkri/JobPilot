# JobPilot --- Implementation Flow

## 1. Development Strategy

Build JobPilot as a sequence of working vertical slices. At the end of
every phase, the project must still start locally and existing tests
must pass.

Do not ask an AI coding assistant to implement the entire repository in
one prompt. Give it one bounded task at a time, require it to inspect
the relevant documentation, and review the generated code.

## 2. Prerequisites

Install: - Git - Python 3.12 or a currently supported Django-compatible
version - Node.js LTS - npm - Docker Desktop with Compose - Ollama - VS
Code or another IDE

Verify:

``` bash
git --version
python --version
node --version
npm --version
docker --version
docker compose version
ollama --version
```

Choose and pin compatible package versions during Phase 0. Do not
blindly use unpinned latest dependencies in a reproducible project.

## 3. Repository Initialization

``` bash
mkdir JobPilot
cd JobPilot
git init

mkdir docs backend frontend automation ai scripts
```

Place the project documentation in `docs/`.

Create `.gitignore` entries for: - `.env` - virtual environments -
`node_modules` - Python cache - local database volumes - uploaded
resumes - generated resumes - browser profiles - model files - logs -
local secrets

Never commit real resume files or browser sessions.

## 4. Phase 0 --- Foundation

### Backend

Create a Python virtual environment and install a pinned baseline:

``` bash
cd backend
python -m venv .venv
```

Activate the environment, then install Django, Django REST Framework,
PostgreSQL driver, Celery, Redis client, environment configuration, API
schema tooling, and test dependencies.

Suggested packages to evaluate: - Django - djangorestframework -
psycopg - celery - redis - django-environ - drf-spectacular - pytest -
pytest-django

Initialize Django:

``` bash
django-admin startproject config .
```

Create domain apps incrementally:

``` bash
python manage.py startapp core
python manage.py startapp resumes
python manage.py startapp jobs
python manage.py startapp matching
python manage.py startapp ai_engine
python manage.py startapp applications
python manage.py startapp automation
python manage.py startapp dashboard
```

Do not implement all models immediately. Start with health checks and
database connectivity.

### Frontend

``` bash
cd ../frontend
npm create vite@latest . -- --template react-ts
npm install
npm install react-router-dom @tanstack/react-query react-hook-form zod @hookform/resolvers lucide-react
```

Set up Tailwind CSS and the chosen shadcn/ui configuration using its
current official installation instructions. Avoid copying outdated setup
commands.

Create a basic app shell with navigation and an API health indicator.

### Docker

Create Docker Compose services for: - backend - frontend - postgres -
redis - celery-worker - celery-beat - ollama

Add persistent volumes for database and model data. Add a health check
for PostgreSQL, Redis, and Ollama where practical.

### Exit Criteria

-   `docker compose up --build` starts the core stack.
-   Django health endpoint works.
-   React page loads.
-   Django connects to PostgreSQL.
-   Celery worker connects to Redis.
-   Ollama is reachable locally.
-   `.env.example` documents required variables.

## 5. Phase 1 --- Master Resume

Implement in this order:

1.  MasterResume model and migrations.
2.  Secure upload endpoint.
3.  PDF text extraction using PyMuPDF.
4.  DOCX extraction using python-docx.
5.  File validation and SHA-256 hashing.
6.  ResumeFact model.
7.  Parsing service and structured extraction schema.
8.  Review/confirm/edit endpoints.
9.  Resume version handling.
10. Frontend upload and review screens.
11. Tests for valid, invalid, empty, and malformed documents.

Suggested packages: - PyMuPDF - python-docx - pydantic or Django
serializers for structured validation

Important: - Text extraction is not the same as reliable semantic
parsing. - Start with deterministic extraction and a review screen. -
Local LLM assistance can be added after the data model and review
workflow work.

Exit Criteria: The user can upload a resume, inspect extracted facts,
correct them, and activate a version.

## 6. Phase 2 --- Job Discovery

Start with two sources that have a clear permitted access method. Prefer
official APIs, feeds, public career pages, or sources whose terms permit
the intended access.

Do not make LinkedIn or another restricted source a hard dependency.

Implementation order:

1.  JobSource and Job models.
2.  JobSourceListing model.
3.  DiscoveryRun and SourceRun models.
4.  Base source adapter interface.
5.  First source adapter.
6.  Normalizer.
7.  Persistence and deduplication.
8.  Second source adapter.
9.  Celery discovery tasks.
10. Job list/detail APIs.
11. Frontend discovery page.
12. Source-level failure tests.

Suggested packages: - httpx or requests for permitted HTTP requests -
BeautifulSoup for permitted HTML parsing - feedparser for RSS/Atom where
applicable - Scrapy only if crawling complexity warrants it

Avoid unnecessary browser automation for discovery if an accessible
structured feed/API exists.

Exit Criteria: Two sources can independently produce normalized job
records and one source failure does not stop the other.

## 7. Phase 3 --- Filtering and Matching

Implementation order:

1.  SearchPreference model and UI.
2.  Normalize title and location values.
3.  Extract job skills and requirements.
4.  Build a skill alias dictionary.
5.  Implement deterministic skill matching.
6.  Implement title relevance.
7.  Implement experience/seniority compatibility.
8.  Implement remote eligibility evaluation.
9.  Implement weighted score calculation.
10. Persist scoring version and explanation.
11. Add filters and sorting to the frontend.
12. Test known sample resume/job pairs.

Suggested packages: - scikit-learn only if a concrete similarity use
case is needed - rapidfuzz for fuzzy string matching - optional local
embedding model later

Do not introduce vector databases in the MVP without a demonstrated
need.

Exit Criteria: A known fixture set produces explainable and repeatable
match results.

## 8. Phase 4 --- Local AI and Resume Tailoring

### Ollama

1.  Confirm Ollama service is available.
2.  Pull a model appropriate for the machine's RAM/VRAM.
3.  Benchmark latency and output quality.
4.  Create an Ollama provider class.
5.  Add timeout and structured-output handling.
6.  Add model health endpoint.

Do not hardcode a model name throughout the codebase.

### Tailoring

1.  Define a versioned resume JSON schema.
2.  Retrieve user-confirmed facts only.
3.  Select relevant facts for the target job.
4.  Create a prompt that forbids new facts.
5.  Request structured output from Ollama.
6.  Validate schema.
7.  Validate claim-to-source references.
8.  Flag unsupported claims.
9.  Create editable preview.
10. Generate PDF and DOCX.
11. Save immutable output artifacts.

Suggested packages: - Ollama HTTP client or httpx - Pydantic for output
schemas - python-docx for DOCX - ReportLab or HTML-to-PDF tooling for
PDF

Choose one PDF rendering approach and test font/layout behavior before
building multiple templates.

Exit Criteria: A tailored resume can be generated offline after the job
description and Master Resume are available, and unsupported claims
cannot silently pass approval.

## 9. Phase 5 --- Application Tracker

1.  Create Application and ApplicationEvent models.
2.  Define allowed status transitions.
3.  Link each application to a job.
4.  Link the exact tailored resume artifact.
5.  Prevent duplicate active attempts.
6.  Build list/detail APIs.
7.  Build application dashboard.
8.  Add notes and manual status updates.
9.  Test status history and document retention.

Exit Criteria: The user can manage prepared and submitted applications
without losing the exact resume used.

## 10. Phase 6 --- Playwright Automation

Start with local mock application pages.

1.  Install Playwright and browser dependencies.
2.  Create a dedicated browser profile directory.
3.  Create AutomationSession and AutomationLog models.
4.  Implement browser worker lifecycle.
5.  Implement adapter registry.
6.  Implement generic high-confidence field mapping.
7.  Implement resume upload.
8.  Implement assisted mode.
9.  Add pause/cancel behavior.
10. Add submission summary.
11. Add explicit per-application authorization.
12. Add one ATS adapter only after mock tests pass.
13. Implement outcome verification.
14. Test timeout and uncertain submission behavior.

Suggested packages: - playwright - pytest - pytest-playwright if useful
for browser tests

Do not test automatic submission against real employers during initial
development.

Exit Criteria: Assisted mode works on a mock form; automatic mode
submits only after authorization and records verified or uncertain
outcomes accurately.

## 11. Phase 7 --- Integration and Hardening

-   Run full workflow from resume upload to application tracking.
-   Test source failures and partial discovery runs.
-   Test malformed AI output.
-   Test Ollama unavailable.
-   Test browser crash.
-   Test app restart while tasks are queued.
-   Test backup and restore.
-   Review file permissions and local network exposure.
-   Add structured logs without personal data.
-   Document recovery procedures.

## 12. Suggested Environment Variables

Example `.env.example`:

``` dotenv
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=replace-for-local-development
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_DB=jobpilot
POSTGRES_USER=jobpilot
POSTGRES_PASSWORD=replace-me
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=configure-after-benchmark

MEDIA_ROOT=/app/data/media
TIME_ZONE=Asia/Jakarta
```

Use a real generated secret locally. Do not commit `.env`.

## 13. Development Workflow

For every task:

1.  Read the relevant docs.
2.  State the intended change and files.
3.  Implement one bounded vertical slice.
4.  Add or update tests.
5.  Run tests and lint/type checks.
6.  Review migrations and generated files.
7.  Update documentation.
8.  Commit a coherent change.

Suggested Git branch pattern: - `feature/resume-upload` -
`feature/job-source-adapter` - `feature/job-matching` -
`feature/local-ai-tailoring` - `feature/application-tracker` -
`feature/playwright-assisted-mode`

## 14. AI Coding Assistant Instructions

When using an AI coding assistant, provide this instruction:

> Read the relevant files in `docs/` before making changes. Follow the
> existing architecture and business rules. Implement only the requested
> phase/task. Do not invent requirements or add unrelated dependencies.
> Preserve the Master Resume as the source of truth. Never implement
> CAPTCHA bypass, anti-bot evasion, or unauthorized application
> submission. Add tests for changed behavior. Explain the files changed,
> decisions made, commands run, and any remaining limitations. Do not
> claim tests passed unless you actually ran them.

## 15. First Coding Session

The first implementation session should do only the following:

1.  Create repository structure.
2.  Add documentation.
3.  Create backend virtual environment and Django project.
4.  Create React + TypeScript app.
5.  Add Docker Compose with PostgreSQL and Redis.
6.  Add a Django health endpoint.
7.  Verify frontend, backend, and database connectivity.
8.  Commit the foundation.

Do not begin scraping, LLM integration, or Playwright automation in the
first session.
