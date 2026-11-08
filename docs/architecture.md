# JobPilot --- Architecture

## 1. Architectural Style

Use a **Modular Monolith**.

The backend is one Django project with domain-oriented Django apps.
Background workers and browser automation may run as separate processes,
but they share the same codebase and domain contracts initially.

Do not introduce microservices for v1.

## 2. System Context

``` text
User
 |
 v
React + TypeScript
 |
 v
Django REST API -------------------- PostgreSQL
 |                                      ^
 |                                      |
 +--> Domain services -----------------+
 |
 +--> Celery task producer --> Redis --> Celery workers
                                      |       |
                                      |       +--> Job source adapters
                                      |       +--> Resume parsers/exporters
                                      |       +--> Matching services
                                      |       +--> Ollama client
                                      |       +--> Playwright automation
                                      |
                                      +--> Celery Beat scheduler

Django / workers --> Ollama local HTTP API
Workers ----------> permitted external job sources
Playwright --------> supported application websites
```

## 3. Backend App Boundaries

### core

Shared base models, settings, health checks, exceptions, and common
utilities. Avoid turning core into a dumping ground.

### resumes

Owns MasterResume, ResumeFact, Experience, Education, Project, Skill,
document parsing, and resume versioning.

### jobs

Owns JobSource, Job, JobSourceListing, source adapters, normalization,
deduplication, and availability verification.

### matching

Owns job requirement extraction results, scoring, eligibility
evaluation, and match explanations.

### ai_engine

Owns Ollama provider integration, prompt templates, structured output
schemas, model health checks, and AI orchestration. It should not own
candidate or job domain data.

### applications

Owns Application, ApplicationEvent, tailored document associations,
status transitions, and application history.

### automation

Owns AutomationSession, AutomationLog, browser lifecycle, form
detection, field mapping, ATS adapters, and submission workflow.

### dashboard

Read-oriented aggregation for dashboard metrics and recent activity.

## 4. Dependency Rules

-   Django views/serializers call application services; they should not
    contain complex business logic.
-   Domain services may depend on repository/query modules and defined
    interfaces.
-   `jobs` must not depend on Playwright.
-   `resumes` must not depend on a specific LLM vendor.
-   `matching` can use deterministic logic and an AI extraction
    interface, but must not depend on frontend code.
-   `automation` may consume approved resume/application data through
    services; it must not mutate resume facts.
-   `ai_engine` provides model capabilities but must not decide whether
    a claim is factually true.
-   Cross-app imports should use stable service functions or interfaces,
    not private internals.

## 5. Suggested Internal Structure

Example for a domain app:

``` text
apps/jobs/
  models/
  api/
    serializers/
    views/
    urls.py
  services/
    discovery.py
    normalization.py
    deduplication.py
    verification.py
  sources/
    base.py
    source_one.py
    source_two.py
  tasks.py
  selectors.py
  tests/
```

Use a simpler structure where a module is small. Avoid creating empty
abstraction layers without a real need.

## 6. Key Interfaces

### Job source

``` python
from typing import Protocol, Iterable

class JobSourceAdapter(Protocol):
    source_key: str

    def search(self, criteria: dict) -> Iterable[dict]:
        ...

    def parse(self, raw_listing: dict) -> dict:
        ...
```

Each adapter returns source data; a shared normalizer converts it to the
internal Job schema.

### AI provider

``` python
class AIProvider(Protocol):
    def generate_structured(
        self,
        *,
        prompt: str,
        schema: dict,
        model: str | None = None,
    ) -> dict:
        ...
```

### Resume exporter

``` python
class ResumeExporter(Protocol):
    def export_pdf(self, resume_document: dict, destination: str) -> str:
        ...

    def export_docx(self, resume_document: dict, destination: str) -> str:
        ...
```

### Application adapter

See `automation-rules.md` for the full contract.

## 7. Job Discovery Design

1.  Scheduler creates a discovery run.
2.  Each enabled source is invoked independently.
3.  Source adapter fetches permitted listings.
4.  Parser extracts source fields.
5.  Normalizer maps them into common fields.
6.  Deduplication checks source ID, canonical URL, and content
    similarity.
7.  Job and source listing records are persisted.
8.  Requirement extraction is queued.
9.  Matching is calculated against the active candidate profile.
10. Dashboard reads the resulting records.

A source error should be recorded against that source run and must not
cancel other sources.

## 8. Matching Design

Use a hybrid approach: - Deterministic normalization and exact/alias
skill matching. - Optional semantic similarity for descriptions and
experience. - Explicit location eligibility evaluation. - Weighted score
with an explanation.

Do not let an LLM invent a numeric score without transparent inputs.
Store component scores and scoring version.

## 9. Resume Tailoring Design

1.  Retrieve approved facts from a specific Master Resume version.
2.  Retrieve structured job requirements.
3.  Select relevant facts deterministically where possible.
4.  Ask the local model to rewrite and organize only those facts.
5.  Parse structured output.
6.  Validate claim-to-fact references.
7.  Reject or flag unsupported claims.
8.  Render a preview.
9.  User edits and approves.
10. Export PDF/DOCX and store immutable artifact paths.

Store prompt version, model identifier, source resume version, and
validation report.

## 10. Browser Automation Design

Playwright runs in a controlled local process. The API creates an
automation session and queues a worker task. The worker opens the
supported page, detects the adapter, fills recognized fields, and pauses
or proceeds according to the selected mode.

Never blindly retry a submission after a timeout. First inspect the page
or confirmation evidence to determine whether the action may already
have succeeded.

## 11. Runtime and Deployment

Use Docker Compose for: - frontend - backend - postgres - redis -
celery-worker - celery-beat - ollama

Playwright may run in the worker container with browser dependencies
installed, or in a dedicated automation worker. Choose one approach and
document browser profile persistence and local file access.

Persistent volumes: - PostgreSQL data - Ollama model data - resume
uploads - generated documents - browser profile - application logs

Bind the UI/API to localhost. Do not expose PostgreSQL or Redis to the
host unless explicitly needed for development.

## 12. Observability

Record: - discovery run start/end and source result - number of listings
fetched/created/updated/ignored - AI model and prompt version - task
state and error category - automation state transitions - application
verification evidence

Do not log raw resume text, credentials, cookies, or complete
application form contents by default.

## 13. Architectural Decisions

-   Modular monolith instead of microservices.
-   PostgreSQL as the only primary database.
-   Redis used for Celery broker/cache needs, not as persistent business
    storage.
-   Local Ollama provider behind an interface.
-   Playwright adapters for supported application workflows.
-   Master Resume facts are authoritative.
-   Explicit user authorization before automatic submission.
