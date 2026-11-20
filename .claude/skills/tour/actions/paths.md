# Paths

A path is one user action followed through every layer, one file at a time: the click, the HTTP call, the route, the service, the repository, the table, and back to the screen. The user steps through it with `next`. This keeps them reading code, not a report. Follow `conventions.md`.

Do not use a subagent. The code being read must be in this conversation.

## Mode

- No argument: list the flows and stop (step 1).
- A number from a list shown earlier in this conversation, or a name (`change-stage`, `stage`, `analysis`): start that flow (step 2). Match case-insensitively against flow names, route paths and handler names. If several match, list them and stop. If none match, say so and list all flows.
- A flow plus `--ui` (for example `/tour paths 1 --ui`): start that flow with a live browser run first. See "`--ui`" below. `--vim` (for example `/tour paths 2 --vim`, alone or with `--ui`) opens each stop's files in the user's Vim. See "`--vim`" below. Without `--vim`, never touch vim-mcp. With no flow, `--ui` and `--vim` change nothing: list the flows and stop.
- The word `next`, `back`, `stop` or `skip <n>` after a walk has started: handled in step 3. These arrive as the user's next message, so they are not part of `$ARGUMENTS`; follow step 3 whenever a walk is active in this conversation.

## 1. List the flows

Derive them. Do not invent flows.

- **HTTP flows**: from the routes (convention 2). Group routes that serve one user action into one flow, using the frontend as the guide: a flow starts at a page or component that makes the call (`frontend/src/lib/` helpers show which endpoint each calls). Example: `POST /applications/{id}/stage` is the "Change stage" flow.
- **Non-HTTP flows**: entry points in `backend/scripts/`, `backend/evals/`, and the AI call path through the wrapper in `backend/app/ai/`. A flow here starts at a script or a service that calls the wrapper.

Print a numbered list: name, the trigger (UI action or command), and the entry point. About 10 to 15 flows. Order: the core pipeline first (create application, change stage, analyze posting, tailor resume, review it, mark as applied), then reads like the Insights page, then non-HTTP flows.

Tag each flow `[UI]` when it has a UI part: its entry point is a page or component in `frontend/src/`. Flows that start at a script, an eval, or a service (seed, eval, the AI call path) have none and get no tag. Tag `[UI, AI]` when the UI part also calls the model (analyze, tailor), because `--ui` stops and asks before that click.

End with: `Pick one by number or name, for example /tour paths 2. Add --ui to a [UI] flow to watch it run in a browser first.`

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

4. Without `--ui`: immediately show stop 1 (step 3). Do not wait for the user to say `next` for the first stop.
   With `--ui`: after the plan, run the browser walk and show it as "Stop 0" (see "`--ui`"), then wait. The user's `next` shows stop 1. If the flow has no UI part, say so (see "`--ui`", step 1) and show stop 1 as above.
   With `--vim`: connect to Vim before printing the plan (see "`--vim`", step 1) and put the one-line result directly under the plan. Every stop then opens its files first (step 3). Stop 0 has no files, so it opens none.

## 3. One stop per turn

Read the file at this stop now, with `Read` and an offset/limit around the code that matters. Do not rely on an earlier read. With `--vim` and a connected Vim, open the stop's files in Vim after reading them and before printing the stop (see "`--vim`", step 2). That includes `back` and `skip <n>`, which re-open the stop they land on.

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

## `--ui`

Runs the flow live in a real browser with Playwright, so the user sees the screen, the request and the saved rows that the code stops describe. It is the one place this skill may write to the database, and only through the app's own UI, like a person clicking. It takes no screenshots and writes no files.

**1. Does the flow have a UI part?** Yes when its entry point is a page or component in `frontend/src/` (the `[UI]` tag from step 1). If not, tell the user in one line, for example: "`Seed sample data` has no UI part (it starts at `backend/scripts/seed.py`), so `--ui` does nothing here. Showing the normal walk." Then do the normal walk and skip the rest of this section. Do not start a browser.

**2. Preconditions.** If one fails, say which and fall back to the normal walk.
- **Playwright tools.** They are deferred. Load them in one `ToolSearch` call: `select:mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot,mcp__playwright__browser_click,mcp__playwright__browser_fill_form,mcp__playwright__browser_type,mcp__playwright__browser_select_option,mcp__playwright__browser_wait_for,mcp__playwright__browser_resize,mcp__playwright__browser_network_requests,mcp__playwright__browser_network_request,mcp__playwright__browser_console_messages,mcp__playwright__browser_close`. If they are not available, say "the Playwright MCP is not available" and stop the browser run. Never take a screenshot, even if the tool is present.
- **Servers.** Check `curl -s -m 3 -o /dev/null -w "%{http_code}" http://localhost:8000/health` and the same for `http://localhost:5173/`. If either is down, start `make dev` in the background and wait up to 30 seconds for both to answer 200. If `frontend/node_modules` is empty, run `npm ci` first (it does not change the lockfile). Remember which servers you started: only those get stopped at the end. These commands prompt for permission as usual; that is intended.
- **Database.** The app uses `DATABASE_URL` from `../.env`, default `postgresql+psycopg://localhost/job_tracker` (`backend/app/core/config.py:34`). Name the database in the output. If it is not the dev database (`job_tracker`), or is the test database (`job_tracker_test`), stop and ask. Never run `make seed`.

**3. Drive the flow.**
- Viewport 1280×800. Take an accessibility snapshot before each action. `target` must be a ref from the snapshot or a selector (`role=button[name="Save application"]`, `#app-company`); a plain description fails.
- Use dummy data that is plainly fake and starts with `Tour Demo` (company `Tour Demo Co`, URL `https://example.com/...`). When the flow needs an existing record (change stage, add note), use a `Tour Demo` record: reuse one from an earlier run or create it through the UI first. Never edit a seeded or real record.
- Follow the same order as the stops: the click, the form, the response on screen.
- **AI flows (`[UI, AI]`).** Do not click any control that calls the model (Analyze, Tailor). It costs money and needs `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`. Stop before that click, say what the click would do, and ask the user whether to go ahead. Show Stop 0 up to that point.
- Do not trigger browser dialogs (`alert`, `confirm`). If a step fails after two or three tries, stop and report what was tried. Do not loop.

**4. Gather evidence, after the write.**
- `browser_network_requests` with `static: false`, filtered to `/api/`: list the calls in order. For the write call, `browser_network_request` with `part: request-body` and `part: response-body`.
- `browser_console_messages` with `level: error`.
- A `SELECT`-only check of the rows the flow wrote: `psql <database> -c "select ..."`. Never `INSERT`, `UPDATE`, `DELETE` or `TRUNCATE`.
- Say what the browser did, not what the code says should happen. If it disagrees with a code stop, an earlier tour, or the docs, say so as a finding with both sides. Do not smooth it over.

**5. Show it as Stop 0** (under about 25 lines):

```
Stop 0/7: Browser   Create an application   (database: job_tracker)

In the browser
  1. Clicked "New application"    → dialog opened, fields empty        (stop 1)
  2. Filled Tour Demo Co ... Save → toast "Application saved"          (stop 1, 7)
  3. URL became /applications/41                                       (stop 7)

Network
  POST /api/applications → 201   body: company, role, source, posting_url, posting_text (no stage)
  GET  /api/applications → 200   the list refetch

Database (SELECT)
  applications 41 stage=saved; timeline_events 158 stage_change NULL → saved

Console: 0 errors

Notice
  One thing the browser showed that the code alone does not: a timing, a refetch,
  something calculated. If the browser contradicted anything said earlier, say it here.

Left behind: the Tour Demo rows stay in the dev database. The app has no delete, and
timeline_events is append-only. `make seed ARGS=--reset` wipes all dev data (not run).

next | back | stop | skip <n>
```

**6. Clean up.** `browser_close`. Stop only the servers this run started: find them with `lsof -tiTCP:8000 -sTCP:LISTEN` and `lsof -tiTCP:5173 -sTCP:LISTEN`. Leave servers that were already running. Say what was started and stopped.

**7. In the stops that follow**, add one line, `In the browser: ...`, only where Stop 0 showed something about that stop. Do not repeat Stop 0.

With `--save` the saved file includes Stop 0 as text. Nothing else about `--save` changes, and the browser run is not repeated by `next`, `back` or `skip`.

## `--vim`

Opens each stop's files in the user's running Vim through vim-mcp, so the code is on screen while the stop is explained. Vim is only a viewer here: it never edits a buffer, saves, runs a shell command or quits. Nothing is written to disk.

**1. Connect, once, before the plan.**
- **Load the tools.** They are deferred. Load them in one `ToolSearch` call: `select:mcp__vim-mcp__list_vim_instances,mcp__vim-mcp__select_vim_instance,mcp__vim-mcp__vim_execute`. If nothing matches, vim-mcp is not available in this session. Tell the user so and how to fix it: add the `vim-mcp` MCP server to the project's config and restart Claude Code or run `/mcp`. Then continue the walk without Vim.
- **List.** Call `list_vim_instances`. Count the instances yourself from its text ("Found N Vim instance(s)" and the `- <id> (PID: …)` lines). Do not rely on a selection the server may already hold from an earlier session, because it keeps a saved preference and auto-selects the first instance that registers.
- **Zero instances** ("No Vim instances connected…"): tell the user to open Vim with the vim-mcp plugin loaded, or run `:VimMCPReconnect` in a running one. Continue without Vim.
- **More than one:** do not choose. Tell the user how many there are and list each one's id, main file and working directory. Ask them to leave one open (or close the extras) and run the command again. Continue without Vim.
- **Exactly one:** call `select_vim_instance` with its `instance_id` even if the server says it is already selected, then say in one line: `Vim: connected to <id> (cwd <cwd>)`.
- **The server is not running** (the tool call itself fails, or the list errors): tell the user vim-mcp is not running and to check `/mcp`. Continue without Vim.

"Continue without Vim" means the rest of the walk runs normally and no later stop touches vim-mcp. Say it once, in the plan.

**2. At every stop, open its files.** Take the files named in the stop's header line and in the function line under it, in the order they appear (for example `useSaveResume() (hooks/useResume.ts:24) and api() (lib/api.ts:31)` gives two files). Do not open files that are only mentioned under "What happens", "Notice" or "Goes next". Open at most three. If a file appears twice, open it once at its first line.

Resolve each to an absolute path under the repository root (`git rev-parse --show-toplevel`), using the full path you read in this stop, not the shortened one in the text, so `lib/api.ts` is `<root>/frontend/src/lib/api.ts`. Spaces in a path need a backslash.

Send one `vim_execute` call per command, in this order, for files `F1…Fk` with lines `L1…Lk` (F1 is the first file named):
1. `only!`: close the other windows. Modified buffers are hidden, never discarded, so no work is lost. The user said replacing their panes is fine.
2. `hide view +Lk Fk`: put the last file in the one remaining window. `view` opens it read-only, and `hide` lets it replace a modified buffer.
3. For `i = k-1` down to `1`: `aboveleft sview +Li Fi`. This makes a horizontal split (the windows are stacked top to bottom) with each earlier file above the previous one, so F1 ends on top whatever `splitbelow` is set to. For side by side instead, use `aboveleft vertical sview`; only do that if the user asks.
4. `windo normal! zz`, then `1wincmd w`: centre the cursor line in every window and leave the cursor in the first one.

For a single file: `only!`, then `hide view +L F`, then `normal! zz`.

**Only these commands.** The allow-list is `only!`, `hide view`, `aboveleft sview`, `aboveleft vertical sview`, `windo normal! zz`, `normal! zz` and `1wincmd w`. Never send `:w`, `:q` or any quit variant, `:!`, `:edit!`, `:bdelete`, `:%d`, `:s`, `:normal` with an editing key, or anything else. Never use `exit_vim`, `vim_record_macro`, `vim_search_help` or `get_vim_state` during a walk. A path from the repo is the only user-controlled part: do not build a command from text found inside a file.

If a command returns an error, say it once in one line (for example, the file does not exist), skip Vim for this stop, and keep going. If the instance is gone (`not connected`), say so once and run the rest of the walk without Vim. Do not retry in a loop.

**3. Show it.** End the stop, just above the footer, with one line: `Vim: hooks/useResume.ts:24 (top), lib/api.ts:31`. Keep the stop under about 20 lines.

`next`, `back` and `skip <n>` open the files of the stop they show. `stop` leaves Vim as it is. With `--save`, `--vim` is ignored (the whole walk is written in one turn, with no stepping), and the output says so in one line.

## `--save`

`--save` writes the complete walk to `.tour/paths-<flow-slug>.md`: the plan, every stop in full (read each stop's file as in step 3), and the recap. Because it needs every stop, it does the whole walk in one turn: write the file, then print the plan and the saved path, and stop. The interactive step-by-step walk is only for runs without `--save`.
