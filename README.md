# JobPilot --- Implementation Documentation

This folder contains the implementation baseline for JobPilot v1.0.

## Documents

1.  `overview.md` --- product scope, actors, workflows, and MVP
    boundaries.
2.  `architecture.md` --- modular monolith, components, boundaries, and
    runtime architecture.
3.  `database-design.md` --- entities, relationships, constraints, and
    indexing guidance.
4.  `api-guide.md` --- REST API conventions, endpoints, request/response
    examples.
5.  `features-and-requirements.md` --- functional/non-functional
    requirements and acceptance criteria.
6.  `implementation-flow.md` --- phase-by-phase development
    instructions, setup, dependencies, and deliverables.
7.  `automation-rules.md` --- browser automation policies, safety gates,
    state machine, and adapter contracts.

## Recommended reading order

`overview.md` → `features-and-requirements.md` → `architecture.md` →
`database-design.md` → `api-guide.md` → `automation-rules.md` →
`implementation-flow.md`.

## Baseline decisions

-   Local-first, single-user application.
-   Django + Django rest framework.
-   React + TypeScript frontend.
-   PostgreSQL database.
-   Celery ( if needed ) + Redis for asynchronous work.
-   Ollama for local LLM inference.
-   Playwright for permitted browser automation.
-   Modular monolith architecture.
-   Assisted application and explicitly authorized automatic submission.
-   Master Resume is the authoritative source of candidate facts.

## Important implementation rule

Do not implement every phase at once. Build vertical slices, add tests,
and keep the application runnable at the end of each phase. Job sources
and ATS integrations must follow the relevant websites' terms and
technical access restrictions.
