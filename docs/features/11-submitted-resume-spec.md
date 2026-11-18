# Mark as Applied and Submitted Resume

## Overview

Record which resume was sent with each application, require that choice before an application can move to Applied, and show the three workflow steps on the detail page.

## Requirements

### Backend

- Migration adding `applications.submitted_resume_id` with its foreign key to `resumes`
- `POST /applications/{id}/apply` with `{"choice": "base"}` or `{"choice": "tailored", "resume_id": ...}`. It is the only endpoint that performs Saved → Applied. It calls `change_stage()` with the choice in `context`. The generic stage endpoint rejects Saved → Applied with 409
- Guard on Saved → Applied: the request must include a choice
- The chosen resume must be the base resume (which must exist) or an approved tailored resume for this application
- Choosing the base resume saves a snapshot of it (`application_id` set, `ai_call_id` null, status `approved`, the same text). `submitted_resume_id` points to the snapshot, and the snapshot and the stage change happen in the same transaction. Choosing a tailored resume points `submitted_resume_id` at it
- Express the guard as data in the guard structure, alongside the transitions
- A failed guard returns 409 with a clear message
- The application response includes the submitted resume (the snapshot, or the tailored resume) and the applied date
- `allowed_next_stages` for a Saved application omits Applied. The response also carries a `stage_change_hint` ("Apply in step 3 below" for Saved), so the frontend applies no rule of its own
- `GET /applications/{id}/submittable-resumes` returns the base resume and every tailored resume for the application, each with `submittable` and, when false, a `reason` (for example "Approve this draft first")
- A pure function in `services/` that computes the three workflow steps for an application, returned in the application response. Check the rules in this order for each step; "left Saved" means the stage is no longer Saved:
  - Step 1, posting analysis: done when an approved analysis exists; skipped when the application left Saved without one; otherwise current
  - Step 2, tailored resume: done when an approved tailored resume exists (a base snapshot is not a tailored resume); skipped when the application left Saved without one; locked when no approved analysis exists; otherwise current
  - Step 3, mark as applied: done when the application left Saved with a submitted resume; skipped when it left Saved without one (withdrawn); locked when no base resume exists; current when an approved tailored resume exists and the stage is Saved; otherwise available
  - At most one step is current
- Tests: missing choice, draft resume, another application's resume, the valid cases, each step status including an application withdrawn from Saved (skipped, never done), the snapshot being created and unaffected by later base resume edits, and the generic stage endpoint rejecting Saved → Applied

### Frontend

- A "Mark as applied" section on the detail page, between Tailored resume and Timeline. It is a section, not a dialog or a separate page
- The section has four states:
  - Locked: no base resume exists yet; link to the Resume page
  - Open: the stage is Saved; shows "Which resume did you send?" with radio options and a Mark as applied button
  - Done: the application has left Saved with a submitted resume; shows a read-only line with the applied date and which resume was sent
- Not applied: the application was withdrawn from Saved; shows a read-only "Withdrawn before applying" line
- Radio options come from `GET /applications/{id}/submittable-resumes`: the base resume and every tailored resume for this application, each with its date. Options that are not submittable are listed but disabled, with the API's reason shown. The frontend applies no rule
- The Mark as applied button is the primary button only when step 3 is current; otherwise it is a secondary button
- The Change stage control renders the options and the hint the API returns. For an application in Saved, that is Withdrawn only, with the hint "Apply in step 3 below". Applied happens through this section, so the resume question cannot be skipped
- A three-step strip under the header showing each step's status from the API: a check for done, a highlighted border for current, a dashed border for locked, available or skipped, and one line of status text
- List page: add a "Resume sent" column (Base, Tailored, or "Not sent yet")

## References

- `@docs/project-overview.md` (Features B: Guards)
- `@docs/architecture.md` (State and guards)
- `@docs/features/03-stages-timeline-spec.md`
- `@docs/screenshots/detail-step-1.png`, `detail-step-2.png`, `detail-step-3.png` (step strip and Mark as applied section in each state)
- `@docs/screenshots/applications-list.png` (Resume sent column)

## Notes

- The frontend holds no step logic. It renders the statuses the API returns.
- Do not show keyword coverage beside the radio options, even though the screenshots do.
- Other transitions are unchanged.
- The submitted resume cannot be changed after the application leaves Saved.
- A base-resume snapshot is not a tailored resume. It never appears in the tailored-resume list, in retrieval or in the AI metrics.
- Applications moved to Applied before this feature have no submitted resume. Reset the development database after this migration.
