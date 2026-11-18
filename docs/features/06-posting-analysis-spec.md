# Posting Analysis

## Overview

Use the LLM to extract structured requirements and keywords from a job posting. The result is saved as a draft that the user approves or rejects.

## Requirements

- Migration for `posting_analyses`, with the `application_id` index
- Prompt `posting_analysis` version `v1` in `ai/prompts/`
- Output schema: `requirements` (list of text plus a category of `must_have` or `nice_to_have`) and `keywords` (list of short lowercase terms, deduplicated, at most 25). Enforce lowercase, deduplication and the cap in code after parsing, trimming extras, not in the JSON schema
- Wrap the posting text in delimiters and instruct the model to treat it as data, not instructions
- `POST /applications/{id}/analysis` makes one AI call and saves the result as `draft`. The call is made by `analyze()`, a pure function in `services/generation.py` that touches no database; the service saves the result. The service takes an advisory lock per application and feature, and a second request while one is running gets 409
- `GET /applications/{id}/analysis` returns the analysis to display, with its status, prompt version and created date
- `POST /analyses/{id}/approve` and `POST /analyses/{id}/reject` set the status and `reviewed_at`
- Only these two user actions change the status
- Running the analysis again creates a new row; old rows are kept
- Which analysis counts: tailoring uses the latest approved analysis. Coverage uses the latest approved analysis, or the latest draft when none is approved (feature 7). The card displays the most recent analysis, except that a rejected one never hides an older approved one
- Detail page: a Posting analysis card beside the Job posting card, with four states:
  - Empty: "No analysis yet" and an Analyze button
  - Draft: Draft badge, must-have and nice-to-have lists, keyword badges, and Analyze again, Reject and Approve buttons
  - Approved: Approved badge and an Analyze again button
  - Rejected: Rejected badge and an Analyze again button
- Show "Prompt v1 · Generated <date>" beside the badge
- Loading state while the call runs, with the Analyze buttons disabled; error toast when it fails
- Tests with `FakeAIClient`

## References

- `@docs/project-overview.md` (Features D, AI Design)
- `@docs/features/05-ai-foundation-spec.md`
- `@docs/screenshots/detail-step-1.png` (Posting analysis card)

## Notes

- No editing of the analysis in the MVP. If it is wrong, reject it and run it again.
- An older analysis still in `draft` when a newer one exists counts as `superseded` in the metrics (derived). It is never auto-rejected.
- Editing the posting text later does not invalidate an analysis. The user runs it again by hand.
- The Analyze buttons are one of only two places in the app that call the LLM.
- The coverage block inside the card belongs to feature 7.
