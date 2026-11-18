# Example Retrieval

## Overview

Before tailoring, find past applications with similar postings and include their approved tailored resumes in the prompt as examples. This is the retrieval step of the RAG pattern, done with PostgreSQL full-text search.

## Requirements

- Migration adding `applications.posting_tsv` as a generated column with a GIN index
- An `ExampleRetriever` interface and a `FullTextRetriever` implementation, so vector search can replace it later
- Build the search query from the approved analysis keywords, combined with OR. Quote multi-word keywords so they stay phrases
- Rank matches with `ts_rank` and take the top 3
- Only consider applications that have an approved tailored resume; use the most recently approved one. A base-resume snapshot is not a tailored resume
- Exclude the application being tailored
- Add the examples to the prompt's examples section, each labeled with that posting's keywords, with a line stating they show style and emphasis only and are not a source of facts. This fills a section that `tailor_resume` v1 already has, so the prompt version does not change
- Record the example resume ids in `ai_calls.retrieved_example_ids`
- When nothing matches, tailoring runs with no examples
- In the Tailored resume section header, show "N past examples used" for the displayed resume
- Tests against a real PostgreSQL test database: ranking order, the exclusion rules and the empty case

## References

- `@docs/project-overview.md` (AI Design: Retrieval)
- `@docs/features/08-tailored-draft-spec.md`
- `@docs/screenshots/detail-step-2.png` ("2 past examples used")
- PostgreSQL full-text search: https://www.postgresql.org/docs/16/textsearch.html

## Notes

- Do not use `plainto_tsquery` on the keyword list. It requires every term to match and returns nothing.
- Prefer `websearch_to_tsquery` with `or` between terms. It accepts raw input such as `c++` or `ci/cd` without syntax errors. The English configuration drops punctuation (`c++` becomes `c`), which is accepted for the MVP.
- This feature is the first to drop if the schedule slips. Keep it isolated behind the interface. Nothing after it depends on it.
