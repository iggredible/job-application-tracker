# Keyword Coverage

## Overview

Calculate, in plain code, which posting keywords appear in a resume and which are missing. No AI is involved.

## Requirements

- A pure function `keyword_coverage(keywords, resume_text)` returning covered keywords, missing keywords and a ratio
- Matching is case-insensitive and whitespace-normalized
- Match on word boundaries so `java` does not match `javascript`
- Handle terms with punctuation: `c++`, `ci/cd`, `.net`, `node.js`
- Multi-word keywords match as a phrase
- `GET /applications/{id}/coverage` with an optional `resume_id` (defaults to the base resume). The response always has `covered`, `missing` and `ratio`. When `resume_id` is given it also has `base` (the same fields for the base resume), `newly_covered` and `still_missing`, so feature 10 needs no change to the endpoint
- Use the latest approved analysis, or the latest draft if none is approved. A rejected analysis is never used
- Coverage is calculated on request and never stored
- In the Posting analysis card: "Keyword coverage, base resume" with the percentage, the count (for example "6 of 10"), a progress bar, and Covered and Missing keyword badges
- When no base resume exists, show a link to the Resume page in place of the numbers
- Unit tests for boundaries, punctuation, phrases and empty input

## References

- `@docs/project-overview.md` (Features D, Derived Values)
- `@docs/screenshots/detail-step-1.png` (coverage block in the Posting analysis card)

## Notes

- Do not call this an "ATS score" anywhere in code or UI.
- This function is reused by the review flow and the eval.
