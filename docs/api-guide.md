# JobPilot --- API Guide

## 1. API Conventions

Base path: `/api/v1/`

-   JSON request and response bodies unless downloading a file.
-   UUID identifiers.
-   ISO 8601 timestamps with timezone.
-   Pagination for collection endpoints.
-   Consistent validation errors.
-   Long-running operations return a task/run identifier.
-   Never return local absolute filesystem paths to the browser.

Suggested pagination:

``` json
{
  "count": 120,
  "next": "http://localhost:8000/api/v1/jobs/?page=2",
  "previous": null,
  "results": []
}
```

Suggested error response:

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be validated.",
    "details": {
      "field": ["A valid value is required."]
    }
  }
}
```

## 2. Resume Endpoints

  Method   Endpoint                     Purpose
  -------- ---------------------------- ------------------------------
  POST     `/resumes/upload/`           Upload PDF/DOCX
  GET      `/resumes/`                  List versions
  GET      `/resumes/active/`           Get active version
  GET      `/resumes/{id}/`             Get version details
  PATCH    `/resumes/{id}/`             Update editable profile data
  POST     `/resumes/{id}/reprocess/`   Re-run parsing
  GET      `/resumes/{id}/facts/`       List facts
  PATCH    `/resume-facts/{id}/`        Edit/confirm/reject a fact

Upload uses `multipart/form-data` with a `file` field.

Example response:

``` json
{
  "id": "UUID",
  "filename": "master-resume.pdf",
  "version_number": 1,
  "parsing_status": "pending",
  "uploaded_at": "2026-11-06T10:00:00Z"
}
```

## 3. Job Endpoints

  Method   Endpoint                       Purpose
  -------- ------------------------------ -----------------------------------
  GET      `/jobs/`                       List/filter jobs
  GET      `/jobs/{id}/`                  Job details
  POST     `/jobs/discover/`              Start discovery
  GET      `/jobs/discovery-runs/`        List discovery runs
  GET      `/jobs/discovery-runs/{id}/`   Run details
  POST     `/jobs/{id}/verify/`           Request availability verification
  GET      `/job-sources/`                List sources
  PATCH    `/job-sources/{id}/`           Enable/disable source

Example filters:

``` text
GET /api/v1/jobs/?country_code=ID&work_arrangement=remote&min_match_score=75&published_within_days=7
```

Discovery request:

``` json
{
  "source_keys": ["source_one", "source_two"],
  "search_preference_id": "UUID",
  "force_refresh": false
}
```

Response:

``` json
{
  "discovery_run_id": "UUID",
  "status": "pending"
}
```

## 4. Matching Endpoints

  Method   Endpoint                             Purpose
  -------- ------------------------------------ ---------------------
  POST     `/matching/jobs/{job_id}/analyze/`   Queue analysis
  GET      `/matching/results/`                 List results
  GET      `/matching/results/{id}/`            Result details
  POST     `/matching/recalculate/`             Recalculate results

Example result:

``` json
{
  "job_id": "UUID",
  "overall_score": 82,
  "components": {
    "skills": 90,
    "experience": 75,
    "title": 85,
    "seniority": 80,
    "location": 70
  },
  "eligibility_status": "uncertain",
  "matched_skills": ["Python", "Django", "PostgreSQL"],
  "missing_skills": ["AWS"],
  "uncertain_requirements": ["Remote work eligibility from Indonesia"],
  "scoring_version": "v1"
}
```

## 5. Tailoring Endpoints

  -----------------------------------------------------------------------------------------------
  Method                  Endpoint                                        Purpose
  ----------------------- ----------------------------------------------- -----------------------
  POST                    `/tailoring/jobs/{job_id}/generate/`            Generate tailored
                                                                          resume

  GET                     `/tailored-resumes/`                            List generated resumes

  GET                     `/tailored-resumes/{id}/`                       Get content and
                                                                          validation

  POST                    `/tailored-resumes/{id}/validate/`              Revalidate claims

  PATCH                   `/tailored-resumes/{id}/`                       Save user edits

  POST                    `/tailored-resumes/{id}/approve/`               Approve document

  GET                     `/tailored-resumes/{id}/download/?format=pdf`   Download PDF/DOCX
  -----------------------------------------------------------------------------------------------

Generate request:

``` json
{
  "master_resume_id": "UUID",
  "template_key": "ats_professional"
}
```

Response:

``` json
{
  "tailored_resume_id": "UUID",
  "status": "review_required",
  "task_id": "TASK_ID"
}
```

Approval must fail if unsupported claims remain unresolved.

## 6. Application Endpoints

  ----------------------------------------------------------------------------------------
  Method                  Endpoint                                 Purpose
  ----------------------- ---------------------------------------- -----------------------
  GET                     `/applications/`                         List applications

  POST                    `/applications/`                         Create draft

  GET                     `/applications/{id}/`                    Detail

  PATCH                   `/applications/{id}/`                    Update notes/status
                                                                   where allowed

  GET                     `/applications/{id}/events/`             History

  POST                    `/applications/{id}/start/`              Start workflow

  POST                    `/applications/{id}/authorize-submit/`   Authorize a specific
                                                                   submission
  ----------------------------------------------------------------------------------------

Creating a draft:

``` json
{
  "job_id": "UUID",
  "tailored_resume_id": "UUID",
  "application_mode": "assisted"
}
```

Automatic submission authorization:

``` json
{
  "automation_session_id": "UUID",
  "authorization": true,
  "reviewed_summary_hash": "SERVER_GENERATED_HASH"
}
```

The server must verify that the reviewed summary has not changed since
authorization.

## 7. Automation Endpoints

  -------------------------------------------------------------------------------------
  Method                  Endpoint                              Purpose
  ----------------------- ------------------------------------- -----------------------
  POST                    `/automation/sessions/`               Create session

  GET                     `/automation/sessions/`               List sessions

  GET                     `/automation/sessions/{id}/`          Session status

  POST                    `/automation/sessions/{id}/pause/`    Pause

  POST                    `/automation/sessions/{id}/resume/`   Resume permitted
                                                                workflow

  POST                    `/automation/sessions/{id}/cancel/`   Cancel
  -------------------------------------------------------------------------------------

Create session:

``` json
{
  "application_id": "UUID",
  "mode": "assisted",
  "start_url": "https://example.com/careers/apply"
}
```

Do not accept arbitrary local file paths from the frontend. The backend
resolves the approved resume artifact associated with the application.

## 8. Dashboard and Settings

  Method   Endpoint                          Purpose
  -------- --------------------------------- -----------------------
  GET      `/dashboard/overview/`            Summary metrics
  GET      `/dashboard/activity/`            Recent events
  GET      `/system/health/`                 Health
  GET      `/settings/search-preferences/`   Get preferences
  PUT      `/settings/search-preferences/`   Update preferences
  GET      `/ai/status/`                     Ollama status
  POST     `/ai/test/`                       Test configured model

## 9. Status Codes

-   `200` successful read/update.
-   `201` resource created.
-   `202` asynchronous task accepted.
-   `204` successful deletion where supported.
-   `400` invalid request.
-   `401` unauthenticated.
-   `403` operation not permitted.
-   `404` resource not found.
-   `409` conflicting state or duplicate attempt.
-   `422` semantically invalid workflow.
-   `429` local rate limit if implemented.
-   `500` unexpected server error.

## 10. API Security

Even for a local-only application: - Bind API to localhost. - Use a
local authentication/session boundary. - Apply CSRF protection when
using cookie authentication. - Restrict CORS to the configured frontend
origin. - Validate every UUID and state transition. - Do not expose
secrets or internal paths. - Do not allow arbitrary URLs to become an
unrestricted server-side fetch proxy.
