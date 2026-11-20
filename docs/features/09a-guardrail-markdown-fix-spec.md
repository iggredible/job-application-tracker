# Guardrail Markdown Fix

## Overview

Bug fix for feature 09. The guardrail check flags a fact that is in the base resume, because the base resume wraps it in Markdown bold marks (`**`). The marks stop the phrase match. The fix removes `**` from both sides before they are compared.

## The bug

- The base resume has this line: `**Lead Software Engineer** (Sep 2024 – May 2026) - **Senior** (Aug 2023 – Sep 2024) - **Engineer** (Jun 2021 – Aug 2023)`.
- The model returns the same text in the `title` field of one job, without `**`.
- `check()` looks for that text as a phrase in the base resume. The `**` marks sit between the words, so the phrase is not found.
- The user sees `Title "Lead Software Engineer (Sep 2024 – May 2026) - Senior (...) - Engineer (...)"` in the warning box. Every fact in it is in the base resume.
- Seen on application 42, draft 45. Checked by hand: the title is found when `**` is removed from the base text, and not found when it is kept.

## Requirements

- `_normalize()` in `backend/app/services/guardrail.py` removes every `**` from the text, in addition to what it does now (lowercase, collapse whitespace, treat en and em dashes as hyphens)
- Removing `**` joins nothing and splits nothing: `**Lead** Software` becomes `lead software`. The marks are removed with no space added, so the spaces that were there stay as they were
- The change applies to both sides of every phrase match, so a bold employer, title or skill in the base resume is found, and a bold value in the draft is found in a plain base resume
- No other Markdown mark is removed. Single `*`, `_`, backticks, and link syntax stay as they are
- No change to the matching rule: whole tokens or phrases on word boundaries, never raw substrings. `Go` does not match `Google`, and `5` does not match `2025`
- A value that is not in the base resume is still flagged. The fix must not make the check weaker
- No change to `check()` or `current_flags()` signatures, the `Flag` shape, the stored `guardrail_flags`, the API, the frontend, or any prompt
- Flags already stored on existing drafts do not change. They are as generated. A new draft gets the corrected flags
- Unit tests, written first and confirmed failing for the right reason:
  - The real Cryoport title line, bold in the base and plain in the draft, gives no title flag
  - A bold employer in the base resume gives no employer flag
  - A bold skill in the base resume gives no skill flag
  - A title that is not in the base resume is still flagged when the base resume has bold marks
  - `current_flags` keeps no flag for a bold-in-base value and still keeps a flag for a value that is not in the base
  - The existing `Go` / `Google` and `5` / `2025` tests still pass

## References

- `@docs/features/09-guardrail-spec.md` (the feature this fixes)
- `@backend/app/services/guardrail.py` (`_normalize`, `_found`)

## Notes

- Only `_found()` is affected. Dates and numbers are read from the raw text with regular expressions that already ignore `*` (`(?<!\w)` and `(?<![\w$.,])`), so they need no change.
- The 8 other flags on draft 45 (four skills and four keywords) are not part of this fix. The model reworded things the base resume says in other words, for example "Code review" for "design and code reviews". The check matches exact words, and this fix does not change that.
- The title field holds all three Cryoport roles and their dates, because the base resume has them on one line. The text is correct, so this fix does not change how the model fills the field.
- The warning box on application 42 will not clear after the fix, because its flags are stored as generated. It clears when the user generates a new draft, which is a real AI call.
- No migration, no frontend change and no prompt change, so no new prompt version and no browser check.
- Commit prefix: `fix:`.
