# JobPilot --- Product Overview

## 1. Purpose

JobPilot is a local-first personal job-search assistant. It discovers
software engineering opportunities, evaluates their relevance against a
user's Master Resume, generates fact-grounded tailored resumes, assists
with application forms, and tracks application outcomes.

The system automates repetitive work but preserves user control over
important decisions and submissions.

## 2. Problem Statement

Candidates often search multiple job boards, repeatedly inspect job
descriptions, tailor resumes, complete similar application forms, and
track applications manually. These tasks are fragmented and
time-consuming.

JobPilot centralizes these workflows in one local application.

## 3. Goals

-   Discover relevant software engineering jobs from multiple permitted
    sources.
-   Normalize and deduplicate listings.
-   Filter by job title, location, work arrangement, seniority, and
    freshness.
-   Evaluate skill and experience compatibility.
-   Generate tailored PDF/DOCX resumes using only verified candidate
    facts.
-   Support assisted applications and authorized automatic submission
    where permitted.
-   Track applications and preserve the exact documents used.
-   Run locally without mandatory paid AI APIs or cloud hosting.

## 4. Non-goals for v1

-   Multi-tenant SaaS or public user registration.
-   Guaranteed scraping of every job board.
-   CAPTCHA solving or bypassing anti-bot controls.
-   Universal ATS automation.
-   Automatic answers to legal, immigration, salary, or other
    high-impact questions without user confirmation.
-   Guaranteeing job eligibility or hiring outcomes.
-   Mandatory email, calendar, or paid AI integrations.

## 5. Primary User

One individual software engineering candidate using the application on a
personal computer.

## 6. Search Profile

Initial target locations: - Batam, Indonesia: on-site, hybrid, and
remote. - Singapore: remote, subject to explicit work-location
eligibility. - APAC: remote, subject to country eligibility. -
Global/worldwide: remote, subject to country eligibility. - Thailand:
remote, subject to country eligibility. - Indonesia: remote.

Initial job titles: - Backend Software Engineer - Backend Developer -
Software Engineer - Software Developer - Junior Software Engineer -
Graduate Software Engineer - Python Developer - Django Developer - C#
Developer - .NET Developer - ASP.NET Core Developer - Full Stack
Developer - Web Developer - API Developer - Application Developer -
Associate Software Engineer

All search preferences must be editable.

## 7. Main User Journey

1.  Start JobPilot locally.
2.  Upload a Master Resume in PDF or DOCX format.
3.  Review and correct extracted candidate facts.
4.  Configure search preferences and permitted job sources.
5.  Run scheduled or manual job discovery.
6.  Review normalized and deduplicated listings.
7.  Inspect match score, matched skills, missing skills, and location
    eligibility.
8.  Select a job and generate a tailored resume.
9.  Review the resume and its fact-validation report.
10. Choose assisted application or authorized automatic submission.
11. Review the application result and update the tracker.

## 8. Core Product Modules

  -----------------------------------------------------------------------
  Module                              Responsibility
  ----------------------------------- -----------------------------------
  Resume                              Upload, parse, version, and manage
                                      candidate facts

  Jobs                                Discover, normalize, deduplicate,
                                      and verify job listings

  Matching                            Compare candidate facts with job
                                      requirements

  AI Engine                           Local model integration and
                                      structured generation

  Applications                        Track prepared and submitted
                                      applications

  Automation                          Browser sessions, ATS adapters,
                                      form filling, submission

  Dashboard                           Aggregated status and activity

  Core                                Shared settings, errors, health
                                      checks, and utilities
  -----------------------------------------------------------------------

## 9. Core Product Principles

### 9.1 Fact-grounded generation

The Master Resume and user-confirmed facts are the only sources for
candidate claims. AI may rewrite, summarize, prioritize, and reorder
supported facts. It must not invent skills, dates, employers, metrics,
achievements, or credentials.

### 9.2 Remote eligibility is not inferred

A job labeled "remote" may be restricted to a country or region. Store
advertised work arrangement separately from accepted candidate work
locations. Unknown eligibility must remain unknown.

### 9.3 Source transparency

Every job must retain its original URL, source name, discovery
timestamp, and verification status.

### 9.4 Human control

The user reviews tailored documents. Automatic submission requires
explicit authorization for the specific application. Unsupported or
uncertain application questions pause the workflow.

### 9.5 Local-first privacy

Resume files, candidate profile, generated documents, database, and
browser profile remain local by default. External websites are contacted
only for discovery and application tasks.

## 10. MVP Definition

The MVP is complete when it can: - Import and review a Master Resume. -
Discover jobs from at least two permitted sources. - Normalize and
deduplicate listings. - Filter by configured preferences. - Calculate
explainable match scores. - Generate and validate tailored resumes using
Ollama. - Export PDF and DOCX. - Track applications. - Launch Playwright
for supported forms. - Fill known fields in assisted mode. - Submit only
after explicit authorization and only where permitted. - Persist task
and application history across restarts.

## 11. Constraints

-   Internet access is required for job discovery and external
    application websites.
-   Local LLM performance depends on available RAM/CPU/GPU.
-   Some sources may block automated access or prohibit scraping.
-   ATS pages change; adapters require maintenance.
-   Local execution is not zero-cost in electricity, hardware, or
    internet usage.
