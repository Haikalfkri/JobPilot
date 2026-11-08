# JobPilot --- Database Design

## 1. Conventions

-   PostgreSQL is the primary database.
-   Use UUID primary keys for records that may be referenced across
    modules or exported.
-   Use timezone-aware timestamps.
-   Use `created_at` and `updated_at` where appropriate.
-   Use foreign keys and database constraints for integrity.
-   Use JSONB only for flexible metadata or snapshots, not for core
    relational facts.
-   Store files on local persistent storage; store their relative paths
    and metadata in PostgreSQL.
-   Do not store passwords, browser cookies, or access tokens in
    plaintext database fields.

## 2. Core Entities

### CandidateProfile

Represents the single local candidate profile.

Fields: - id: UUID, primary key - full_name: string - email: string,
nullable - phone: string, nullable - professional_summary: text,
nullable - linkedin_url: URL, nullable - github_url: URL, nullable -
portfolio_url: URL, nullable - created_at, updated_at

### MasterResume

Represents an uploaded resume version.

Fields: - id: UUID - version_number: integer - original_filename:
string - storage_path: string - file_type: enum(pdf, docx) - sha256:
string - extracted_text: text - parsing_status: enum(pending,
processing, completed, failed, review_required) - is_active: boolean -
uploaded_at: timestamp

Constraints: - Unique version_number. - Unique file hash may be used to
warn about duplicate uploads. - Only one active Master Resume at a time;
enforce in service logic and, where practical, a conditional unique
constraint.

### ResumeFact

A normalized, traceable candidate fact.

Fields: - id: UUID - master_resume_id: FK - category: enum(personal,
summary, experience, education, skill, project, certification, language,
link) - fact_key: string, nullable - content: text - structured_value:
JSONB, nullable - source_location: string, nullable -
verification_status: enum(parser_suggested, user_confirmed, rejected) -
created_at, updated_at

A parser suggestion is not equivalent to a verified fact.

### Experience

Fields: - id: UUID - master_resume_id: FK - company_name: string -
position_title: string - description: text - start_date: date,
nullable - end_date: date, nullable - is_current: boolean -
employment_type: string, nullable

### Education

Fields: - id: UUID - master_resume_id: FK - institution: string -
degree: string, nullable - field_of_study: string, nullable -
start_date: date, nullable - end_date: date, nullable

### Skill

Fields: - id: UUID - master_resume_id: FK - name: string -
normalized_name: string - category: string, nullable - proficiency:
string, nullable - evidence_fact_id: FK ResumeFact, nullable

### Project

Fields: - id: UUID - master_resume_id: FK - name: string - description:
text - technologies: JSONB or related ProjectTechnology rows -
project_url: URL, nullable - start_date/end_date: date, nullable -
evidence_fact_id: FK ResumeFact, nullable

## 3. Job Discovery Entities

### JobSource

Fields: - id: UUID - key: unique string - display_name: string -
source_type: enum(api, feed, public_page, company_career_page, manual) -
base_url: URL, nullable - is_enabled: boolean - configuration: JSONB -
created_at, updated_at

Do not store credentials in the general configuration JSON. Use
environment variables or a local secret store when credentials are
required.

### Job

Represents the normalized job identity.

Fields: - id: UUID - title: string - normalized_title: string -
company_name: string - description: text - location_text: string,
nullable - country_code: string, nullable - work_arrangement:
enum(remote, hybrid, onsite, unknown) - remote_eligibility:
enum(worldwide, apac, country_specific, region_specific, unknown,
not_applicable) - eligible_countries: JSONB, nullable - employment_type:
enum(full_time, contract, internship, part_time, unknown) -
experience_level: enum(graduate, junior, associate, mid, senior,
unknown) - salary_min: numeric, nullable - salary_max: numeric,
nullable - salary_currency: string, nullable - published_at: timestamp,
nullable - discovered_at: timestamp - last_verified_at: timestamp,
nullable - status: enum(active, expired, closed, unknown) -
description_hash: string - created_at, updated_at

### JobSourceListing

Preserves each source listing for a normalized job.

Fields: - id: UUID - job_id: FK Job - source_id: FK JobSource -
external_id: string, nullable - original_url: URL - canonical_url: URL,
nullable - raw_metadata: JSONB, nullable - first_seen_at: timestamp -
last_seen_at: timestamp - last_checked_at: timestamp, nullable -
source_status: enum(active, closed, unknown)

Constraints: - Unique (source_id, external_id) when external_id is
present. - Index canonical_url. - Index job_id and source_id.

### JobSkill

Fields: - id: UUID - job_id: FK - skill_name: string - normalized_name:
string - requirement_type: enum(required, preferred, optional) -
importance: numeric, nullable

### DiscoveryRun

Fields: - id: UUID - started_at, finished_at - status: enum(pending,
running, completed, partial, failed) - trigger_type: enum(scheduled,
manual) - summary: JSONB

### SourceRun

Fields: - id: UUID - discovery_run_id: FK - source_id: FK - status:
enum(running, completed, partial, failed, skipped) - fetched_count:
integer - created_count: integer - updated_count: integer - error_code:
string, nullable - error_summary: text, nullable - started_at,
finished_at

## 4. Matching Entities

### JobMatch

Fields: - id: UUID - job_id: FK - master_resume_id: FK -
scoring_version: string - overall_score: numeric - skill_score:
numeric - experience_score: numeric - title_score: numeric -
seniority_score: numeric - location_score: numeric - eligibility_status:
enum(eligible, ineligible, uncertain, not_assessed) - matched_skills:
JSONB - missing_skills: JSONB - uncertain_requirements: JSONB -
explanation: text - calculated_at: timestamp

Constraint: - Unique (job_id, master_resume_id, scoring_version) if only
one current result per scoring version is desired; otherwise retain
calculation history with a separate run identifier.

## 5. Resume Tailoring Entities

### TailoredResume

Fields: - id: UUID - job_id: FK - master_resume_id: FK - version_number:
integer - generated_content: JSONB - validation_report: JSONB -
pdf_path: string, nullable - docx_path: string, nullable - model_name:
string - prompt_version: string - status: enum(generated,
review_required, approved, rejected) - created_at, updated_at

### ResumeClaim

Fields: - id: UUID - tailored_resume_id: FK - claim_text: text -
source_fact_ids: JSONB - validation_status: enum(supported,
partially_supported, unsupported, requires_confirmation) -
validation_notes: text, nullable

Do not permit export as an approved final resume while unsupported
claims remain unresolved.

## 6. Application Entities

### Application

Fields: - id: UUID - job_id: FK - tailored_resume_id: FK, nullable -
application_mode: enum(assisted, automatic) - status: enum(draft,
ready_for_review, awaiting_submission, submitting, submitted,
submission_failed, verification_required, interview, rejected,
withdrawn, no_response) - application_url: URL, nullable - submitted_at:
timestamp, nullable - last_status_changed_at: timestamp - notes: text,
nullable - created_at, updated_at

Add an application uniqueness rule based on job identity and user
intent. Do not rely on URL alone because URLs may change. Allow an
explicit retry/new attempt only after reviewing the previous attempt.

### ApplicationEvent

Fields: - id: UUID - application_id: FK - event_type: string -
description: text - metadata: JSONB, nullable - created_at: timestamp

Append events rather than overwriting historical events.

## 7. Automation Entities

### AutomationSession

Fields: - id: UUID - application_id: FK - adapter_key: string -
browser_name: string - mode: enum(assisted, automatic) - state: string -
started_at, finished_at - outcome: string, nullable - error_code:
string, nullable - error_summary: text, nullable

### AutomationLog

Fields: - id: UUID - session_id: FK - action_key: string - state:
enum(started, completed, failed, skipped, paused) - safe_details: JSONB,
nullable - created_at

Never store passwords, cookies, full tokens, or sensitive form answers
in logs.

## 8. Preferences and AI Configuration

### SearchPreference

Fields: - id: UUID - name: string - job_titles: JSONB - keywords:
JSONB - target_locations: JSONB - work_arrangements: JSONB -
employment_types: JSONB - experience_levels: JSONB -
minimum_match_score: integer - publication_window_days: integer -
discovery_enabled: boolean - created_at, updated_at

### AIConfiguration

Fields: - id: UUID - provider_key: string - model_name: string -
base_url: string - temperature: numeric - max_tokens: integer,
nullable - is_active: boolean - updated_at

## 9. Relationships Summary

-   MasterResume 1---many ResumeFact
-   MasterResume 1---many Experience
-   MasterResume 1---many Education
-   MasterResume 1---many Skill
-   MasterResume 1---many Project
-   JobSource 1---many JobSourceListing
-   Job 1---many JobSourceListing
-   Job 1---many JobSkill
-   Job 1---many JobMatch
-   Job 1---many TailoredResume
-   TailoredResume 1---many ResumeClaim
-   Job 1---many Application attempts, subject to duplicate protection
-   Application 1---many ApplicationEvent
-   Application 1---many AutomationSession
-   AutomationSession 1---many AutomationLog

## 10. Indexing

Recommended indexes: - Job(status, published_at) -
Job(normalized_title) - Job(country_code, work_arrangement) -
Job(description_hash) - JobSourceListing(source_id, external_id) -
JobSourceListing(canonical_url) - JobMatch(master_resume_id,
overall_score) - Application(status, created_at) - Application(job_id) -
AutomationSession(application_id, started_at)

Use PostgreSQL full-text search or trigram indexes only after query
patterns justify them.

## 11. File Storage

Suggested local paths:

``` text
data/
  resumes/original/
  resumes/tailored/pdf/
  resumes/tailored/docx/
  browser-profiles/
  backups/
```

Store relative paths in the database. Use generated UUID-based filenames
rather than trusting uploaded filenames as storage paths.
