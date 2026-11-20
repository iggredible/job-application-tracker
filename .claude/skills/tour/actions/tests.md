# Tests

An inventory of what the tests assert, grouped by feature, written as behaviors. It answers "what is this app guaranteed to do?" without reading 800 test functions. Follow `conventions.md`.

## Mode

- No argument: overview of every feature.
- A feature number, name or keyword (`3`, `stages`, `guardrail`): every behavior for that feature, in full.
- A test file name: every test in that file, as behaviors.

## Facts

Get the test list from commands (convention 2): backend `def test_` lines with `file:line`, frontend `it(`/`test(` lines with their enclosing `describe(` and `file:line`. The test name is the behavior's source. Read the test body only when the name is unclear.

Map each test file to a feature:

1. From the `docs/features/NN-*-spec.md` titles, build the list of features.
2. Assign each test file to the feature whose spec names it, or whose subject its file name matches (for example `test_transitions.py` and `test_stage_service.py` belong to stages). When a file does not fit, put it under "Cross-cutting" (architecture, logging, AI client, seed) or "Unmapped". Never force a guess.

## Overview

Map in a subagent (convention 4). For each feature, in spec order:

```
Tour tests | ...stamp

## 3. Stages and timeline        backend 41 tests in 5 files, frontend 12 in 1
- A stage change outside the allowed transitions returns 409 and lists the allowed next stages  (`tests/test_stages_api.py:NN`)
- Changing stage writes one timeline event in the same transaction  (`tests/test_stage_service.py:NN`)
- ... up to about 8 behaviors per feature: the ones that state a rule, not the plumbing
- (33 more: /tour tests 3)
```

Then:

- **Cross-cutting**: architecture rules, request logging, AI client, seed, eval. Same format.
- **Gaps** (only if real): features with a spec and no tests; routes from the OpenAPI list with no test mentioning the path or handler; services with no test file. State the evidence for each.
- **How the tests are built** (two or three lines, once): which tests hit a real database, which use fakes (`tests/fakes.py`), and that AI calls are mocked per CLAUDE.md. Cite `conftest.py` or the fake.
- **Counts**: backend tests, frontend tests, by feature.

Write each behavior as a sentence about what the app does, not as the function name. A reader should learn the rule without opening the test. Prefer behaviors that state a rule or an error case over "returns 200".

## Feature mode

All behaviors for the feature, grouped by test file, each with `file:line`, in the same sentence form. Mark the ones that pin down a CLAUDE.md "must never be broken" rule. End with the routes and services those tests cover, linked by name, and suggest `/tour paths <flow>` for the main one.
