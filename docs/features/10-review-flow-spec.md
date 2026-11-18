# Tailored Resume Review

## Overview

Let the user compare a draft with the base resume, edit it, and approve or reject it. The original draft is preserved so the amount of editing can be measured.

## Requirements

- In the Tailored resume section: the base resume (read-only) and the draft side by side
- The draft is an editable textarea while its status is `draft`, with a Save edits button
- `PATCH /resumes/{id}` saves edits to `content_markdown` only, and only while the status is `draft`
- `draft_markdown` never changes after creation
- `POST /resumes/{id}/approve` and `POST /resumes/{id}/reject` set the status and `reviewed_at`
- Approve saves any unsaved edits first
- Approved and rejected resumes are read-only
- An approved resume shows an Approved badge, "Approved <date>" (with "after your edits" when it was edited), and a Copy Markdown button that copies its text to the clipboard
- Below the panes: "Keyword coverage X% → Y%" comparing the base resume with the current draft text, with "Newly covered" and "Still missing" keyword lists
- The coverage endpoint returns both lists when given a `resume_id`
- Which resume the section displays: the newest draft if one is awaiting review; otherwise the latest approved; otherwise the latest rejected. The API makes this choice: `GET /applications/{id}/tailored-resumes` marks one resume as `displayed`, and the frontend renders it
- Saving edits returns the updated coverage and current guardrail flags. They update on save, not while typing, because the frontend holds no rules
- A service helper that derives the outcome: pending, superseded, approved, edited then approved, or rejected. A draft that is still `draft` but has a newer draft for the same application and feature is superseded, not pending
- A service helper that derives the edit ratio from `draft_markdown` and `content_markdown` as 1 − `difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()`, so 0 means unedited
- Outcome and edit ratio are calculated, never stored
- Tests for edit rules, status changes and both helpers, including a draft that becomes superseded and an edit ratio on text longer than 200 characters

## References

- `@docs/project-overview.md` (Features E, Derived Values)
- `@docs/features/07-keyword-coverage-spec.md`
- `@docs/screenshots/detail-step-2.png` (draft in review)
- `@docs/screenshots/detail-step-3.png` (approved, read-only state)

## Notes

- No diff highlighting and no "regenerate with feedback". To try again, reject and tailor again.
- "2 past examples used" in the screenshot belongs to feature 12.
