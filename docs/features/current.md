# Current Feature: 11 Mark as Applied and Submitted Resume

## Status

<!-- Not started | Planned | In progress | Completed -->

Not started

## Goals

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

## Decisions

<!-- Choices made while planning or building, with the reason. -->

## Notes

- The frontend holds no step logic. It renders the statuses the API returns.
- Do not show keyword coverage beside the radio options, even though the screenshots do.
- Other transitions are unchanged.
- The submitted resume cannot be changed after the application leaves Saved.
- A base-resume snapshot is not a tailored resume. It never appears in the tailored-resume list, in retrieval or in the AI metrics.
- Applications moved to Applied before this feature have no submitted resume. Reset the development database after this migration.
- Spec: `docs/features/11-submitted-resume-spec.md`
- References: `docs/project-overview.md` (Features B: Guards), `docs/architecture.md` (State and guards), `docs/features/03-stages-timeline-spec.md`
- Screenshots: `docs/screenshots/detail-step-1.png`, `detail-step-2.png`, `detail-step-3.png` (step strip and Mark as applied section in each state), `docs/screenshots/applications-list.png` (Resume sent column)

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
- 03 Stages and Timeline (2026-11-18): enforced stage transitions and guards as data, `change_stage()` as the only stage writer, an append-only timeline with notes, and stage counts, filter, last activity and stale tags on the list.
- 04 Base Resume (2026-11-18): one editable Markdown base resume, kept to a single row by a unique partial index, behind `GET` and `PUT /resume` and an editor page with a "How this is used" panel.
- 05 AI Foundation (2026-11-19): one AI client wrapper with structured outputs and a database call log (`ai_calls`, append-only, written in its own transaction), typed errors, a price table, an in-memory sink and a test fake; no UI.
- 06 Posting Analysis (2026-11-19): one AI call turns a posting into a draft analysis (requirements and keywords) that the user approves or rejects, behind four endpoints, a lock per application and a card on the detail page.
- 07 Keyword Coverage (2026-11-19): a pure `keyword_coverage()` function and `GET /applications/{id}/coverage` that measure the base resume against the posting keywords, shown as a percentage, progress bar and Covered and Missing badges on the Posting analysis card.
- 08 Tailored Resume Draft (2026-11-19): one AI call writes a structured draft from the base resume and the approved keywords, rendered to Markdown by code and saved as a `draft` behind `POST` and `GET /applications/{id}/tailored-resumes`, with two guards, a lock per application, a `draft_markdown` trigger and a Locked, Ready and Draft section on the detail page.
- 09 Guardrail Check (2026-11-19): a pure `check()` flags employers, titles, dates, numbers, skills and keywords that the base resume lacks and stores them as generated in `resumes.guardrail_flags`, and a pure `current_flags()` recalculates what the user sees, shown as a warning box above the draft.
- 10 Tailored Resume Review (2026-11-19): the user edits a draft beside the base resume, then approves or rejects it behind `PATCH /resumes/{id}` and `POST /resumes/{id}/approve` and `/reject`, with outcome, edit ratio and the displayed resume calculated on request, never stored.
