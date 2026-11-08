# JobPilot --- Browser Automation Rules

## 1. Purpose

This document defines safe and predictable browser automation for job
applications.

Automation is intended to reduce repetitive data entry. It must not
bypass access controls, misrepresent the candidate, or submit
applications without the required authorization.

## 2. Supported Modes

### Assisted Mode

1.  Open the application URL.
2.  Detect supported fields.
3.  Fill fields with confirmed profile data.
4.  Upload the approved tailored resume.
5.  Display filled and unanswered fields.
6.  Pause for the user.
7.  User reviews and submits manually.

### Automatic Mode

1.  Perform the same preparation as assisted mode.
2.  Validate all required fields and answers.
3.  Display a complete submission summary.
4.  Obtain explicit authorization for this specific application.
5.  Submit only if the adapter and website workflow permit it.
6.  Verify the outcome.
7.  Record the result and evidence.

Authorization for one application does not authorize other applications.

## 3. Prohibited Behaviors

The automation must not: - Solve or bypass CAPTCHA. - Bypass MFA or
login challenges. - Evade bot detection or access restrictions. - Use
stolen, shared, or unauthorized sessions. - Submit to a website when its
terms prohibit the automation. - Invent candidate information. - Guess
work authorization, sponsorship, salary, demographic, or legal
answers. - Repeatedly submit after an uncertain timeout. - Claim success
based only on clicking a button.

If a site presents a challenge or blocks automation, pause and request
manual user action.

## 4. Field Confidence

Every detected field should be classified:

-   `high`: field label and mapping are unambiguous and value comes from
    confirmed profile data.
-   `medium`: likely mapping, but requires user review.
-   `low`: ambiguous or unsupported.

Only high-confidence mappings may be autofilled automatically. Medium
and low-confidence fields must be shown for review.

## 5. Sensitive and High-Impact Questions

Examples: - Work authorization. - Visa sponsorship. - Security
clearance. - Salary expectations. - Disability or demographic
questions. - Criminal history declarations. - Availability/start date
where not configured. - Years of experience when the question's
definition is unclear.

These require explicit user-provided answers or confirmation. Do not
infer from nationality, residence, resume dates, or other indirect
signals.

## 6. Adapter Contract

``` python
from typing import Protocol

class ApplicationAdapter(Protocol):
    key: str

    async def can_handle(self, page) -> bool:
        ...

    async def inspect_form(self, page) -> dict:
        ...

    async def fill_known_fields(self, page, profile: dict, resume_path: str) -> dict:
        ...

    async def validate_form(self, page) -> dict:
        ...

    async def submit(self, page) -> dict:
        ...

    async def verify_outcome(self, page) -> dict:
        ...
```

`submit` must only be called after the application service has validated
authorization and adapter eligibility. The adapter itself must not
create authorization.

## 7. Adapter Selection

Selection order: 1. Exact supported ATS adapter. 2. Generic adapter for
high-confidence standard fields. 3. Manual-only fallback.

An adapter must not claim support solely because the page URL contains a
familiar brand name. Inspect the actual form and supported structure.

## 8. Automation State Machine

``` text
PENDING
  -> INITIALIZING
  -> NAVIGATING
  -> DETECTING_FORM
  -> FILLING_FORM
  -> VALIDATING_FORM
       -> REVIEW_REQUIRED (assisted)
       -> READY_TO_SUBMIT (automatic)
            -> AUTHORIZATION_REQUIRED
            -> SUBMITTING
            -> VERIFYING
                 -> SUBMITTED
                 -> VERIFICATION_REQUIRED
                 -> SUBMISSION_FAILED
```

Any state may transition to `PAUSED`, `CANCELLED`, or `FAILED` where
appropriate.

## 9. Idempotency and Retry Rules

Safe to retry: - Job page inspection. - Form detection. - Reading public
listing details. - Resume generation when a new version is explicitly
requested.

Retry with caution: - Form filling, after checking current field
values. - File upload, after checking whether the file is already
attached.

Do not automatically retry: - Submit action after timeout or browser
disconnection. - Any action where the application may already have been
received.

After uncertain submission: 1. Reopen or inspect the current page if
safe. 2. Look for a confirmation page, reference number, or confirmation
message. 3. Check available application history if provided by the
website. 4. If inconclusive, set `verification_required`. 5. Do not
submit again automatically.

## 10. Evidence and Logging

Record: - Adapter key and version. - Application and session IDs. -
State transitions. - Fields filled by category, not sensitive raw
values. - Resume artifact ID. - User authorization timestamp and
reviewed summary hash. - Submission attempt timestamp. - Verification
result and safe evidence metadata.

Do not record: - Passwords. - Session cookies. - Authentication
tokens. - Full sensitive answers. - Full page HTML containing personal
information unless explicitly needed for local debugging and protected.

Screenshots may contain personal data. If retained, keep them local,
restrict access, and provide a retention/deletion policy.

## 11. Browser Profile and Session

-   Use a dedicated JobPilot browser profile.
-   Do not reuse a personal everyday browser profile.
-   Keep profile files in a local persistent directory.
-   Do not export cookies or credentials into logs.
-   Let the user sign in manually when needed.
-   Pause on MFA and other authentication challenges.

## 12. Local Test Strategy

Build mock application pages locally before integrating real ATS
platforms.

Test: - Standard text fields. - Select controls. - Checkboxes. - Radio
groups. - File uploads. - Required-field validation. - Ambiguous
labels. - Unsupported questions. - CAPTCHA-like pause behavior using a
mock challenge. - Browser disconnect during submission. - Confirmation
page detection. - Duplicate submission prevention.

## 13. Definition of Done

An adapter is ready only when: - Its supported page structure is
documented. - It passes local mock tests. - It identifies unsupported
questions. - It never bypasses access controls. - It respects
assisted/automatic mode boundaries. - It handles uncertain submission
safely. - It records accurate outcomes.
