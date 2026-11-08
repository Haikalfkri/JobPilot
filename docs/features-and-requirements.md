# JobPilot --- Features and Requirements

## 1. Requirement Conventions

-   **Must:** required for MVP.
-   **Should:** important but can follow the first working slice.
-   **Could:** optional enhancement.
-   Each requirement has an identifier for traceability.

## 2. Functional Requirements

### FR-RES-01 --- Master Resume Upload (Must)

The user can upload PDF or DOCX files.

Acceptance: - Reject unsupported file types. - Enforce configurable
file-size limits. - Store files in a local persistent volume. - Record
file hash, filename, type, and upload timestamp. - Never expose uploaded
files through an unrestricted static directory.

### FR-RES-02 --- Resume Parsing (Must)

Extract text and structured candidate facts from the uploaded file.

Acceptance: - Preserve extracted raw text for troubleshooting. - Parse
contact details, summary, skills, experience, education, projects,
certifications, and links where available. - Mark uncertain extraction
for user review. - Do not silently treat model-inferred details as
verified facts.

### FR-RES-03 --- Resume Fact Review (Must)

The user can edit, confirm, or reject extracted facts.

Acceptance: - Each fact has a source and verification state. -
User-confirmed facts are distinguishable from parser suggestions. - The
active Master Resume version is explicit.

### FR-RES-04 --- Resume Versioning (Must)

Replacing a Master Resume creates a new version.

Acceptance: - Historical tailored resumes retain a reference to the
exact source version. - Existing application artifacts are not
overwritten.

### FR-JOB-01 --- Job Source Adapters (Must)

The system supports a common adapter interface for job sources.

Acceptance: - At least two compliant sources are integrated for MVP. -
Each source can fail independently. - Each listing stores source
identity and original URL. - Access restrictions and source terms are
respected.

### FR-JOB-02 --- Job Normalization (Must)

Map source-specific data into a common Job model.

Acceptance: - Normalize title, company, location, work arrangement,
description, URL, dates, and source. - Preserve raw source payload only
where useful and permitted. - Mark missing values as unknown rather than
inventing them.

### FR-JOB-03 --- Duplicate Detection (Must)

Identify the same job across repeated crawls and syndicated sources.

Acceptance: - Prefer source + external ID when available. - Also compare
canonical URL and normalized content signals. - Preserve multiple source
references where the same job appears on multiple sources. - Avoid
merging unrelated roles solely because titles match.

### FR-JOB-04 --- Job Freshness and Verification (Must)

Track publication, discovery, and last verification timestamps.

Acceptance: - Distinguish active, expired, closed, and unknown. - Do not
claim a listing is open based only on a stale search snippet. - Failed
verification should result in unknown, not automatically closed.

### FR-FILTER-01 --- Search Preferences (Must)

The user can configure job titles, keywords, countries, work
arrangements, seniority, employment type, freshness window, and minimum
match score.

Acceptance: - Filters can be combined. - Preferences persist locally. -
Remote eligibility is separate from advertised work arrangement.

### FR-MATCH-01 --- Requirement Extraction (Must)

Extract required and preferred skills, experience expectations, title,
seniority, and location constraints.

Acceptance: - Keep required and preferred qualifications separate. -
Mark ambiguous requirements as uncertain. - Store extraction/model
version for reproducibility.

### FR-MATCH-02 --- Explainable Matching (Must)

Calculate a compatibility score and explain the result.

Initial weights: - Technical skills: 35% - Experience relevance: 25% -
Job title relevance: 15% - Seniority compatibility: 15% - Location
compatibility: 10%

Acceptance: - Weights are configurable. - Missing and unknown skills are
distinct. - The score is an estimate, not a probability of hiring. - A
hard location restriction can flag a job as ineligible or uncertain
independently of the numeric score.

### FR-AI-01 --- Local AI Provider (Must)

Use Ollama through a local service abstraction.

Acceptance: - Model name and endpoint are configurable. - Backend checks
model availability. - Invalid JSON, timeout, and model-unavailable
errors are handled. - No paid API is required for normal MVP workflows.

### FR-AI-02 --- Resume Tailoring (Must)

Generate a job-specific resume from approved candidate facts.

Acceptance: - Rewriting, summarizing, and reordering are allowed. -
Unsupported skills, achievements, dates, employers, and metrics are
prohibited. - Generated claims reference source facts. - User can review
and edit before approval. - Export PDF and DOCX.

### FR-AI-03 --- Claim Validation (Must)

Validate generated statements against source facts.

Acceptance: - Claims have supported, partially supported, unsupported,
or requires-confirmation states. - Unsupported claims are excluded from
final export until corrected. - Validation is not delegated solely to
the same LLM that generated the claim.

### FR-APP-01 --- Application Tracker (Must)

Track jobs the user intends to apply to and applications submitted.

Acceptance: - Link application to job and exact tailored resume. -
Record mode, timestamps, status, and notes. - Preserve status history. -
Prevent accidental duplicate applications.

### FR-AUTO-01 --- Assisted Application (Must)

Open a supported application page, fill confidently identified fields,
upload the resume, and pause for user submission.

Acceptance: - Show which fields were filled. - Show fields left
unanswered. - User manually submits. - Store session outcome.

### FR-AUTO-02 --- Authorized Automatic Submission (Must, limited)

Submit only on supported workflows that permit automation and only after
explicit per-application authorization.

Acceptance: - Show a submission summary before authorization. - Pause
for CAPTCHA, MFA, login challenges, uncertain answers, and unsupported
forms. - Never bypass anti-bot protections. - Verify receipt where
possible. - If receipt cannot be verified, record verification required
rather than submitted.

### FR-AUTO-03 --- ATS Adapters (Should)

Provide adapter-specific handling for supported ATS platforms.

Acceptance: - Adapter identifies its supported form version/structure. -
Generic fallback handles only high-confidence fields. - Adapter failures
do not corrupt application state.

### FR-TASK-01 --- Background Jobs (Must)

Run discovery, parsing, matching, document generation, and browser
workflows asynchronously.

Acceptance: - Task status and errors are persisted. - Retry only
safe/idempotent operations. - Browser submission is not blindly retried
after an uncertain outcome.

### FR-DASH-01 --- Dashboard (Must)

Display discovered jobs, matching jobs, prepared applications, submitted
applications, interviews, and recent activity.

Acceptance: - Counts are derived from persisted records. - Dashboard
reflects task failures and stale data where relevant.

## 3. Non-Functional Requirements

### NFR-SEC-01 --- Local Security

-   Bind services to localhost by default.
-   Keep PostgreSQL and Redis ports private to the Docker network.
-   Protect API endpoints with local authentication or a strong local
    access boundary.
-   Keep secrets out of source control.
-   Validate uploaded files.
-   Avoid logging resume contents, passwords, cookies, or tokens.

### NFR-PRIV-01 --- Data Privacy

-   Store resume files and browser profiles locally.
-   Do not send resume content to third-party AI APIs.
-   Explain that job websites receive data the user submits to them.
-   Provide local backup and deletion controls.

### NFR-REL-01 --- Reliability

-   Source failures are isolated.
-   Background task state survives restart.
-   Persistent files use Docker volumes.
-   Backups can be restored.

### NFR-PERF-01 --- Performance

-   Long-running operations must not block API requests.
-   Discovery and AI tasks run in workers.
-   Paginate job and application lists.
-   Use database indexes for common filters.

### NFR-MAINT-01 --- Maintainability

-   Keep domain logic out of Django views.
-   Use service and adapter interfaces.
-   Add unit tests for scoring, normalization, and validation.
-   Version prompts and extraction schemas.

## 4. MVP Priority

  Feature                           Priority
  --------------------------------- ---------------------------------
  Master Resume upload and review   P0
  Two job source adapters           P0
  Normalization and deduplication   P0
  Search filters                    P0
  Explainable matching              P0
  Ollama integration                P0
  Fact-grounded tailored resume     P0
  PDF/DOCX export                   P0
  Application tracker               P0
  Assisted browser application      P0
  Authorized automatic submission   P1, only for validated adapters
  Additional ATS integrations       P2
  Email notifications               P2
  Interview preparation             P3

## 5. Definition of Done for Each Feature

A feature is complete only when: 1. Its business rules are implemented.
2. API validation and error handling exist. 3. Relevant automated tests
pass. 4. Frontend loading, empty, success, and error states exist where
applicable. 5. Documentation is updated. 6. No secrets or personal
resume data are committed.
