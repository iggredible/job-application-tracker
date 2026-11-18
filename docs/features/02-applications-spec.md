# Applications CRUD

## Overview

Create, list, view and edit job applications. The posting text is pasted in by hand.

## Requirements

- Migration for the `applications` table and the `source` and `stage` enums, without `posting_tsv` and `submitted_resume_id` (later features add them)
- New applications start in stage `saved`
- `POST /applications`, `GET /applications`, `GET /applications/{id}`, `PATCH /applications/{id}`
- `PATCH` can change company, role, posting URL, posting text and source only
- No delete endpoint
- Follow the layering: route → service → repository
- Pydantic schemas for create, update and read
- List page at `/`: title with the application count, a New application button, and a table with company (links to the detail page), role, source, stage badge and added date
- New application is a dialog on the list page, not a separate route. Fields: company, role, source (dropdown), posting URL (optional), posting text (textarea)
- Saving closes the dialog and opens the new application's detail page. Saving does not run any AI call
- Detail page at `/applications/:id`: header with company, role, source, added date and stage badge; an Edit button; the posting text in a scrollable card with an "Open original" link when a URL exists
- Edit opens the same dialog, pre-filled. The Edit button is on the detail page only; the list has no edit action
- Toast on success and on error
- Service and API tests

## References

- `@docs/project-overview.md` (Features A, Schema)
- `@docs/screenshots/applications-list.png`
- `@docs/screenshots/new-application-dialog.png`
- `@docs/screenshots/detail-step-1.png` (header and Job posting card only)

## Notes

- `stage` is not writable through `PATCH`. It changes only through the stage feature that comes next.
- `GET /applications` returns a plain list here. Feature 3 changes it to an object with the items and the counts.
- Editing the posting text later does not invalidate an analysis made from the old text. The user re-runs it by hand.
- Dev data created in this feature has no timeline events. Feature 3 backfills them or the development database is reset.
- The stage filter, stage counts, last activity and stale tags on the list screenshot belong to feature 3. The "Resume sent" column belongs to feature 11.
