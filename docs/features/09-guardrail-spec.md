# Guardrail Check

## Overview

After tailoring, verify in plain code that every hard fact in the draft exists in the base resume. Anything that does not is flagged for the user.

## Requirements

- Migration adding `guardrail_flags` (JSON, default empty list) to `resumes`
- A pure function `check(tailored, base_text, keywords)` returning a list of flags, each with a field, a value and a message
- Flag an employer or title value that is not found in the base resume
- Flag a dates value when a year or month in it is not in the base resume. Years are whole tokens, months are compared by their first three letters, and "Present" and "Current" are ignored
- Flag a skill that is not found in the base resume
- Flag any number in the summary or a bullet whose token is not in the base resume. A number token is digits with optional `,` `.` `$` `%` and a trailing `k`, `m` or `x`
- Flag an approved analysis keyword that appears in the draft (summary, bullets or skills) but not in the base resume
- Normalize before comparing: lowercase, collapse whitespace, treat en and em dashes as hyphens
- Match whole tokens or phrases on word boundaries, never raw substrings: `Go` does not match `Google`, and `5` does not pass because `2025` exists
- Run the check in the same service call as generation and store the result in `guardrail_flags`. The stored flags are as generated and never change
- A pure function `current_flags(flags, content_markdown, base_text, keywords)` that recalculates what the user sees. A structural flag (employer, title, dates, skill) stays only while its value still appears in the text. Number and keyword flags are recalculated from the text. The API returns the current flags with each resume
- Flags never block approval and are never auto-fixed
- In the Tailored resume section, above the draft: a warning box titled "N things in this draft are not in your base resume", listing each flag, for example `Skill "Kubernetes"`, with the line "Edit or remove them, or keep them if they are true. Flags do not block approval."
- The box lists the current flags, so it updates when the user edits and saves
- No box when there are no current flags
- Unit tests: one per flag type, a clean draft with zero flags, the number-token case, the `Go` / `Google` case, a reformatted date that must pass, a number in the summary, a keyword in the draft but not in the base, and `current_flags` after a flagged skill is removed

## References

- `@docs/project-overview.md` (AI Design: Guardrail Check)
- `@docs/screenshots/detail-step-2.png` (warning box)

## Notes

- `check` runs once, on the model's structured output. `guardrail_flags` keeps those flags as generated, and metrics read them so prompt versions are compared fairly. `current_flags` follows the user's edits, and the user sees those.
- A flag is about the draft. A keyword the posting wants and the resume lacks is a missing keyword, which belongs to coverage.
