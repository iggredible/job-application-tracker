# Stages and Timeline

## Overview

Move applications through the hiring pipeline with enforced transitions, and record every change in an append-only timeline.

## Requirements

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

## References

- `@docs/project-overview.md` (Features B: transition table and guards)
- `@docs/architecture.md` (State and guards)
- `@docs/screenshots/applications-list.png`
- `@docs/screenshots/detail-step-1.png` (header and Timeline section)

## Notes

- Interview rounds are timeline notes under Interviewing, not separate stages.
- Real guards are added in features 8 and 11. Feature 11 adds the apply action and removes Applied from the options of a Saved application.
- Notes count as activity, so adding a note resets the stale clock. This is intended.
