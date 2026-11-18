# Tailored Resume Draft

## Overview

Use the LLM to write a tailored resume from the base resume and the posting. The output is structured JSON, rendered to Markdown by code and saved as a draft.

## Requirements

- Migration adding to `resumes`: `ai_call_id` (foreign key to `ai_calls`), `content_json` and `draft_markdown`, plus a trigger that rejects any change to `draft_markdown` after insert
- Prompt `tailor_resume` version `v1` in `ai/prompts/`
- Prompt inputs: rules, base resume, posting text, approved analysis keywords, and an examples section. The section is part of v1 from the start and stays empty until feature 12, so filling it later is not a new prompt version
- Rules in the prompt: only rephrase, reorder and emphasize facts from the base resume; never invent experience, skills, employers, titles, dates or metrics; if a required skill is missing from the resume, leave it missing
- Output schema `TailoredResume` from the overview: summary, experiences (employer, title, dates, bullets) and skills
- A deterministic renderer that turns the structured output into Markdown. It splits the base resume by headings. A section headed Summary, Experience or Skills (case-insensitive) is replaced by the model's output, and all other sections, including any text before the first heading, are copied through unchanged. If the base has no such heading, the generated section is added after the header
- `POST /applications/{id}/tailored-resumes` makes one AI call and saves a resume row. The call is made by `tailor()`, a pure function in `services/generation.py` that touches no database. The service takes an advisory lock per application and feature, and a second request while one is running gets 409
- Guard: the application must have an approved posting analysis, otherwise 409 with the reason
- A base resume must exist, otherwise 409 with the reason
- Save `content_json`, `draft_markdown`, `content_markdown` (same as the draft at first), status `draft` and `ai_call_id`
- `GET /applications/{id}/tailored-resumes` lists them, newest first, each with status, prompt version and created date
- Multiple drafts per application are allowed. A new draft does not change the status of older ones. An older draft still in `draft` counts as `superseded` in the metrics (derived, never auto-rejected)
- Detail page: a Tailored resume section below the posting and analysis cards, with these states:
  - Locked: a dashed box with a lock icon, "Approve the posting analysis to unlock tailoring", and a disabled Tailor resume button
  - Ready: the same box without the lock, and an enabled Tailor resume button
  - Draft: Draft badge, "Prompt v1 · Generated <date>", a Tailor again button, and the rendered draft shown read-only
- Loading state while the call runs, with the Tailor buttons disabled; error toast when it fails
- Tests: both guards, the renderer and the persisted fields

## References

- `@docs/project-overview.md` (Features E, AI Design: Tailored Resume Output Schema)
- `@docs/architecture.md` (AI call path)
- `@docs/features/05-ai-foundation-spec.md`
- `@docs/screenshots/detail-step-1.png` (locked Tailored resume box)
- `@docs/screenshots/detail-step-2.png` (section header and draft pane)

## Notes

- Register the analysis guard in the guard structure from feature 3, under its own action.
- Retrieval fills the examples section in feature 12. Tailoring must work with no examples.
- The Tailor buttons are the second of only two places in the app that call the LLM.
- Flags, editing, the base resume pane, coverage and Approve / Reject come in features 9 and 10.
