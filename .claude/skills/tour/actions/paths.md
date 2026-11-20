# Paths

A path is one user action followed through every layer, one file at a time: the click, the HTTP call, the route, the service, the repository, the table, and back to the screen. The user steps through it with `next`. This keeps them reading code, not a report. Follow `conventions.md`.

Do not use a subagent. The code being read must be in this conversation.

## Mode

- No argument: list the flows and stop (step 1).
- A number from a list shown earlier in this conversation, or a name (`change-stage`, `stage`, `analysis`): start that flow (step 2). Match case-insensitively against flow names, route paths and handler names. If several match, list them and stop. If none match, say so and list all flows.
- The word `next`, `back`, `stop` or `skip <n>` after a walk has started: handled in step 3. These arrive as the user's next message, so they are not part of `$ARGUMENTS`; follow step 3 whenever a walk is active in this conversation.

## 1. List the flows

Derive them. Do not invent flows.

- **HTTP flows**: from the routes (convention 2). Group routes that serve one user action into one flow, using the frontend as the guide: a flow starts at a page or component that makes the call (`frontend/src/lib/` helpers show which endpoint each calls). Example: `POST /applications/{id}/stage` is the "Change stage" flow.
- **Non-HTTP flows**: entry points in `backend/scripts/`, `backend/evals/`, and the AI call path through the wrapper in `backend/app/ai/`. A flow here starts at a script or a service that calls the wrapper.

Print a numbered list: name, the trigger (UI action or command), and the entry point. About 10 to 15 flows. Order: the core pipeline first (create application, change stage, analyze posting, tailor resume, review it, mark as applied), then reads like the Insights page, then non-HTTP flows. End with: `Pick one by number or name, for example /tour paths 2.`

Stop. Do not start a walk without a choice.

## 2. Plan the walk

1. Trace the flow by reading, starting at the entry point and following calls down. Typical order: component → hook → `lib/` helper → HTTP → `api/` handler → service → guards or rules → repository → model or table → (AI wrapper and log sink, if called) → response schema → back to the component that renders it.
2. Decide the stops. One stop is one file, or one function when a file has several that matter. Between 4 and 9 stops. Merge trivial hops (a one-line hook) into the stop before them. Skip layers the flow does not touch, and say so ("this flow never calls the AI").
3. Print the plan first, without reading code aloud:

```
Tour paths | ...stamp

Flow: Change an application's stage  (POST /applications/{id}/stage)
Stops (6):
  1. UI        components/ChangeStageMenu.tsx
  2. API       api/applications.py
  3. Service   services/applications.py   change_stage
  4. Rules     services/transitions.py
  5. Repo      repositories/timeline.py
  6. Table     models/timeline_event.py

Tests that cover this flow: test_stages_api.py, test_stage_service.py, stages.test.tsx
```

Test files come from `Grep` for the route path, the handler, or the service method name in the test directories. List only files that match.

4. Immediately show stop 1 (step 3). Do not wait for the user to say `next` for the first stop.

## 3. One stop per turn

Read the file at this stop now, with `Read` and an offset/limit around the code that matters. Do not rely on an earlier read.

```
Stop 3/6: Service   services/applications.py:156
change_stage()  (`services/applications.py:156`)

What happens
  Two to four lines, plain language, each with its own file:line.

Notice
  One thing worth seeing: a rule from CLAUDE.md or architecture.md at work,
  a pattern, or a trap. With file:line. Name a Rails equivalent if one helps.

Goes next
  services/transitions.py:19: the rules table that decides what is allowed.

next | back | stop | skip <n>
```

Rules:

- One stop only, then wait. Keep it under about 20 lines.
- "Notice" is one thing, not a list. Prefer the thing the user would otherwise miss: where a business rule is held, where the transaction starts and ends, where the AI is (or is not) called, what is stored and what is calculated.
- Each stop shows the position as `n/N`.
- `next`: show the following stop. `back`: show the previous stop again (read it again). `skip <n>`: jump to stop n. `stop`: end the walk with the recap below, then stop.
- If the user asks a question mid-walk, answer it briefly with file:line, then show the same stop's footer again. Do not advance.
- If the code has changed since the plan (a line no longer matches), re-read, correct the stop, and say so.

## 4. Recap

After the last stop, or on `stop`: a chain diagram of the whole flow (about ten nodes at most), then:

- **Where the rules live**: one line each for the business rules this flow touches, with `file:line`.
- **Tests that pin this flow down**: the test names with `file:line`. Offer `/tour tests <feature>` for the full list.
- **Doc drift**: only if the walk revealed a disagreement with the docs.
- **Nearby flows**: one or two other flows that share files with this one.

## `--save`

`--save` writes the complete walk to `.tour/paths-<flow-slug>.md`: the plan, every stop in full (read each stop's file as in step 3), and the recap. Because it needs every stop, it does the whole walk in one turn: write the file, then print the plan and the saved path, and stop. The interactive step-by-step walk is only for runs without `--save`.
