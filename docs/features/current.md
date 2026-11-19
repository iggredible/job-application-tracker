# Current Feature: 03 Stages and Timeline

## Status

<!-- Not started | Planned | In progress | Completed -->

Planned

## Goals

- Move applications through the hiring pipeline with enforced transitions, and record every change in an append-only timeline.
- Migration for `timeline_events` and the `event_type` enum, with the `(application_id, created_at)` index and a trigger that rejects UPDATE and DELETE
- The same migration adds an initial `saved` event for applications created in feature 2 (or reset the development database)
- Define allowed transitions as data (one mapping in `services/`), not as if-statements
- Add a guard structure beside it, keyed by action (a stage transition, or another gated step such as starting tailoring). Each guard is a function `(context) -> None | GuardFailure`. `context` carries the application, its related records and any extra input. Empty for now
- `ApplicationService.change_stage(application_id, to_stage, *, context=None)` validates the transition, runs the guards, updates `applications.stage` and inserts a timeline event in one transaction. The service takes a clock, so tests control "now"
- No other code path may write `applications.stage`. The two exceptions are creating an application (the column default is `saved`) and the seed script (feature 13). An architecture test checks this
- Creating an application writes an initial event (`from_stage` null, `to_stage` saved)
- `POST /applications/{id}/stage`, `POST /applications/{id}/notes`, `GET /applications/{id}/timeline`
- An invalid transition returns 409 with the list of allowed next stages
- No update or delete for timeline events, in the API or the repository. A test confirms the database trigger rejects both
- The application response includes `allowed_next_stages` and `last_activity_at` (the newest timeline event)
- A single stale rule in `services/`, using the injected clock: an application is stale when its stage is not terminal and its last activity is 14 or more days old. The response includes `is_stale` and the number of idle days
- `GET /applications` accepts a `stage` filter. The response changes from a plain list to an object: `items`, `counts_by_stage` and `stale_count`. The counts cover all applications, not only the filtered ones
- Detail page: a Change stage control in the header listing only the allowed next stages
- Detail page: a Timeline section at the bottom, newest first, with an Add a note field and button
- List page: a row of stage filter pills (All plus one per stage) with counts; clicking one filters the table
- List page: replace the added date column with Last activity; stale rows show a "Stale, N days" tag
- List page: a one-line notice above the table when any application is stale
- Tests: every allowed transition, a sample of disallowed ones, terminal stages, the event is written, a failed transition writes nothing, and the stale rule

## Decisions

<!-- Choices made while planning or building, with the reason. -->

- Backfilled `saved` events use each application's `created_at`, so last activity stays accurate for existing rows.
- Notes are trimmed and a blank note returns 422; there is no maximum length (the spec sets none).
- `idle_days` is whole days, rounded down, and is always an integer; `is_stale` is a separate flag. The stale rule lives only in `services/staleness.py`.
- `counts_by_stage` (all 8 stages, zeros included) and `stale_count` cover all applications and ignore the `stage` filter, so the pills and the notice stay stable while filtering.
- If an application has no timeline event, `last_activity_at` falls back to its `created_at`.
- List order is unchanged (newest created first); the screenshot's order is not a spec requirement.
- The selected stage filter lives in the URL (`/?stage=applied`) so Back from a detail page keeps it.
- Guard failures map to 409 with the reason. No real guards exist yet (features 8 and 11).
- Saved applications list Applied in the Change stage control for now, per the spec table; feature 11 removes it. The "Apply in step 3 below" hint is not built.
- Request bodies: stage `{ "to_stage": ... }`, notes `{ "note": ... }`. A 409 returns `detail: {message, allowed_next_stages}`.
- Stage changes apply on click with no confirmation, because the spec lists none. Terminal stages cannot be undone (a mistake is corrected by a note).
- `change_stage()` locks the application row (`SELECT ... FOR UPDATE`) so two concurrent changes cannot both pass validation.
- The only place that assigns `Application.stage` is `ApplicationRepository.update_stage()`, called only by `change_stage()`. The architecture test scans `app/` with `ast` to enforce this.
- The `dropdown-menu` and `alert` shadcn components are added through the shadcn CLI. No new npm packages: `radix-ui` is already installed.
- The browser check uses hand-made applications and backdated SQL inserts for stale rows, since seed data arrives in feature 13.

## Notes

- Interview rounds are timeline notes under Interviewing, not separate stages.
- Real guards are added in features 8 and 11. Feature 11 adds the apply action and removes Applied from the options of a Saved application.
- Notes count as activity, so adding a note resets the stale clock. This is intended.

References:

- `docs/project-overview.md`: Features B (transition table and guards), Data Architecture (`timeline_events` schema, append-only triggers), Derived Values
- `docs/architecture.md`: State and guards, Data principles, Testing
- `docs/screenshots/applications-list.png`: stage pills with counts, stale notice, Last activity column and stale tag
- `docs/screenshots/detail-step-1.png`: header with Change stage control, and the Timeline section
- Spec: `docs/features/03-stages-timeline-spec.md`

Screenshot content outside this spec (the spec wins, so do not build it here):

- List: the "Resume sent" column and the "6 in progress" subtitle
- Detail: the step strip, the "Apply in step 3 below" hint, the posting and analysis cards, Tailored resume and Mark as applied sections

## History

- Doc review before feature 1: resolved contradictions between CLAUDE.md, the overview, the architecture and the specs, and fixed design gaps (snapshot, guardrail holes, metrics rules).
- 01 Project scaffold (2026-11-18): FastAPI health check with request logging, Alembic baseline, React app shell, Makefile, Procfile and CI; all checks green.
- 02 Applications CRUD (2026-11-18): create, list, view and edit applications through a shared dialog, with a service and repository behind four endpoints; stage is not editable here.
