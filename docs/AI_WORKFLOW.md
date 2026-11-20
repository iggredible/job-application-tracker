# AI Workflow

How this app was built from a written specification using Claude Code.

## Approach

<!-- DRAFT by Claude from the feature log and the repo history. Needs the author's review: it is written in the author's voice. -->

I wrote the specification before any code and let it drive the work, one feature per session, in numeric order. Four kinds of document carried it:

- `docs/project-overview.md` says what to build and why: the domain rules, the schema, the AI design and the UI guidelines.
- `docs/architecture.md` says how it is put together: the layers, which steps are deterministic and which call the model, and the key decisions. It is updated whenever the structure changes, so it describes the code as built.
- `docs/features/NN-*-spec.md` is one spec per feature, small enough to build and check in a session. `docs/features/current.md` holds the status and the decisions of the feature in progress, so a new session can pick it up.
- `CLAUDE.md` holds the rules that must never be broken (stage changes only through `change_stage()`, append-only logs, derived values never stored, AI output always a draft) and the workflow itself.

Each feature went through the same loop, as a `/feature` skill with one action per step:

1. **Load.** Claude reads the spec and the files it references, writes the goals into `current.md` and commits that.
2. **Plan.** Claude proposes the files, the tests named after the requirements, and the assumptions it would make. It writes no code until I approve, and I often changed the plan here (feature 17's `v2` prompt was narrowed to tailoring only at this step). The approved plan and its decisions are committed.
3. **Start.** A branch, the tests first, a check that they fail for the right reason, then the code, then `make test` and `make lint`. For a frontend feature, a walk through the feature in a real browser with Playwright against the seed data, compared with the screenshot.
4. **Test, review, complete.** The checks run again. A review, ideally by a subagent that has not seen the build session, ranks findings by severity, and I decide which to fix. Then the work is recorded and committed, and I merge.

Because plans, specs and decisions are committed as they are made, the history shows the process, not only the result.

## How I verified the work

**Read line by line.** I read these five areas of the code, and this is what each one does in my own words:

- **The prompts.** I added a v2 tailoring prompt on top of v1. There was an issue with a posting analysis v2, so only the tailoring prompt has a v2.
- **The guardrail.** It adds deterministic checks on the model's output.
- **The stage rules.** They put the transition rules in data, instead of complicated if/else conditions.
- **The database triggers.** A rule in PostgreSQL stops any update or delete on `timeline_events` and `ai_calls`, so they work as append-only logs.
- **The eval.** It calls a real LLM on four dummy postings, and it also runs the keyword coverage and the guardrail on the results.

**Trusted to tests.** Behavior that is plain code with a precise rule: stage transitions and guards, keyword coverage, the guardrail, rendering, edit ratio, metrics and the seed plan are pure functions or services with unit and integration tests against a real PostgreSQL test database. The rules that must never be broken have tests of their own: an architecture test that only `change_stage()` and the documented exceptions write `applications.stage`, trigger tests that UPDATE and DELETE fail on the append-only tables, and a test that only the apply code writes `submitted_resume_id`. No test makes a network call; a guard in the test setup blocks it, and a test proves the guard works against the real SDK.

**Distrusted even when green.** Green tests missed real bugs several times: layout in a browser (feature 2), a missing migration in my dev database (features 10, 11 and 13), a number regex that let `$1.5B` through (feature 9) and a table that stretched a phone screen (feature 15). So I distrusted a first run that passed everything, and had Claude break the code on purpose, one rule at a time, to see that a named test failed (features 12 and 17).

**Checked by hand.** Every frontend feature in a real browser against `make dev` and the seed data, with the console open, and compared with its screenshot. The model was checked against the real API with a smoke script (feature 5), and prompt quality with the eval, run by hand (feature 16).

## Feature log

<!-- Two or three lines per feature, written as each one is finished:
     what the agent got wrong, how it was caught, what was changed as a result. -->

**Doc review before feature 1.** I had Claude read the overview, architecture and all specs and report what was unclear or inconsistent before any code existed. It found real contradictions: the seed script bypassed the `change_stage()` rule, the eval was told to use the AI wrapper while not writing to the database, and spec 7 used a different "which analysis" rule than spec 6. It also found gaps that would have skewed the data: the base resume is editable but "what I sent" pointed at it, the tailored schema dropped education and contact details, and the guardrail missed the summary and matched substrings. I answered twelve questions (all with the recommended defaults) and the fixes went into the docs in a handful of small commits (see `git log`), so the specs now agree with each other before the first line of code.

**Feature 01, project scaffold.** The setup tools pulled in packages I had not approved. `shadcn init` defaulted to Base UI instead of Radix, and it and the Tailwind and eslint setups also added `cn`, a Geist font package, `@tailwindcss/vite` and `@eslint/js`, none of them in the approved list. Claude switched the init to Radix and wrote the rest into the decisions, but only the review step showed that nobody had actually approved them; I approved them after the review and added them to the approved list and the spec. The review also found two things green tests had missed: the smoke test never clicked a nav link (and leaked the page between tests, so it passed by luck), and a 500 response had no `X-Request-ID` although its log line did. Each got a failing test first and then a fix, and I checked the click test by breaking a link path and watching it fail. Two versions also had to be pinned because the newest ones did not work together: TypeScript to `~6.0` (typescript-eslint stops below 6.1) and ESLint to 9.

**Feature 02, applications CRUD.** The green tests missed two bugs that I only found by using the app in a browser: a long pasted posting made the dialog's textarea grow past the screen so the Save button could not be reached, and a backend validation error showed in the toast as "body: Value error, posting_url must be…". jsdom cannot test layout, so Claude capped the textarea at `50vh` (checked by hand only), and `api.ts` now strips the Pydantic prefix, with a unit test. The generated `sonner` component imported `next-themes`, which I had not approved, so Claude removed the import and fixed the theme to light instead of adding the package.

**Feature 03, stages and timeline.** The pill-click test showed that the pills and the table blanked out on every click while the new stage loaded; I kept the previous data on screen (`keepPreviousData`) so they stay put. The screenshot's stale notice says "14 or more days", but the API does not send the threshold, so using it would copy a business rule into the frontend; the notice says "no recent activity" instead and the difference is documented.

**Feature 04, base resume.** Two first saves racing would have made two rows, or an error. The unique partial index stops that, and the repository turns the violation into `BaseResumeExists` so the service retries as a replace. Blank text is rejected with 422, because a blank base resume would make tailoring meaningless.

**Feature 05, AI foundation.** The plan used the SDK's `messages.parse()`, which checks the reply against the schema inside the call. A reply cut off mid-way would fail there as a generic validation error, before I could see that it was cut off. Claude switched to `messages.create()`, which checks why the call stopped first and validates the text after. The same read showed the SDK sends requests through `httpx2`, so the planned no-network guard on `httpx` would have blocked nothing; a test now proves the real SDK is blocked. I asked for a smoke script that makes three real calls, and it found what the stub missed: the model can return a `thinking` block before the text, so the stub and two tests now cover it. I chose not to guard a `max_tokens` limit that a one-page resume can't reach.

**Feature 06, posting analysis.** My first frontend tests clicked Analyze before the analysis had loaded and failed three times; the card was fine, so the tests now wait for the button. In the browser, the screenshot meant to show the loading state caught the finished draft, because the real call took only a few seconds; a script that clicks and reads the buttons in one step showed all three disabled. The independent review found that approve and reject did not lock the row, so two tabs could decide the same draft. That got a failing test (a second session holds the row and the other decision must wait) and a `SELECT … FOR UPDATE`, and I checked the test by removing the lock and watching it fail.

**Feature 07, keyword coverage.** My plan said `c++` would not match `c+++`. The first test run showed the word-boundary rule does match it, because `+` is not a word character, so I dropped that case and wrote the rule into the decisions instead of tightening it. Adding the coverage block made the card call two new endpoints, and that broke two older tests whose mock answered every unknown URL with an application; the mock now answers 404 like the real API. In the browser on real data I recounted 13 of 25 with a separate script and it matched. I also saw that the card shows the newest draft's keywords while coverage follows the latest approved analysis, as the spec says.

**Feature 08, tailored resume draft.** The first draft's summary claimed "8 years of backend experience", a number worked out from the dates that the base resume never states, and the mocked tests could not see it; I left the prompt alone, because feature 9's number flag should catch it and the eval in feature 16 should check it before any prompt v2. The "dashed" box rendered solid, because the shadcn Card draws its outline with a ring, so `border-dashed` did nothing; it now swaps the ring for a real dashed border, checked by eye.

**Feature 09, guardrail check.** The independent review found a bug the green tests missed: the number regex backtracked when a figure ended in letters other than k, m or x, so a made-up `$1.5B` was read as `$1` and passed against a base resume that said `$1.2B`. Claude reproduced it with three failing tests first, then made a number token take every letter, digit and `,` `.` `%` glued to it; that widens the spec's "trailing k, m or x" and is written into the decisions. In the browser the sample draft showed four flags where the screenshot shows two, because the spec also flags keywords the draft uses and the base lacks, and the spec wins. Two smaller review findings are left open: `.5` and `US$5M` are never read as numbers, and numeric months such as `01/2021` are not compared. A structural fact the user adds while editing is not re-checked, which is what the spec asks for.

**Feature 10, tailored resume review.** The first time I opened `/resume` it crashed with `column resumes.ai_call_id does not exist`. My dev database was still at migration 0005 while the code expected 0008, and the tests never saw it because they migrate their own database on every run. Running `alembic upgrade head` fixed it, and I now run `make setup` after pulling new migrations. Changing the list to pick the displayed resume with `.find` broke ten older tests, because their mocks answered `/tailored-resumes` with the application object, which the old `drafts?.[0]` had tolerated; I fixed the mocks rather than add defensive code. The plan said PATCH would ignore extra fields, but reusing `ResumeWrite` makes a stray `status` a 422, which I kept because it is stricter. In the browser on real data I checked edit, save, approve with unsaved text (the requests went PATCH then approve), copy and reject. The independent review passed with four minor findings and three nits. The one that mattered was that Tailor again silently threw away unsaved text, which no test had tried; it now stays disabled while the draft has unsaved text, with a test first. I also fixed an ungrammatical 409 message and two missing endpoint descriptions. Left open on purpose: the status badge is outline instead of the green Approved variant, the "Read-only now that it is approved" note is missing, and Save, Reject and Approve sit on their own row instead of beside the coverage line.

**Feature 11, mark as applied and submitted resume.** When I first ran the app, every request failed with `column applications.submitted_resume_id does not exist`: my dev database was still at migration 0008, and the tests could not see it because they migrate their own database. It is the same slip as in feature 10, and `alembic upgrade head` fixed it. Taking Applied off the generic stage path broke a lot of older tests (the new service constructor, moves to Applied through the old endpoint, and a feature 2 test that said the column must not exist), so I changed those tests instead of keeping a back door. My test over every combination of step inputs showed that the spec's own rules give two current steps when a tailored resume is approved without an approved analysis; that state cannot happen, so I limited the test to reachable states and wrote it into the decisions. The row lock that stops a double apply had only a sequential test until `/feature test`, when I added a two-session one. The independent review passed with four minor findings and two nits, and I chose to skip all of them: the tailored section still decides its own lock, a refused second apply says "cannot move from applied to applied", the disabled option is faded not dashed, and two small layering points. In the browser I applied with the base and the tailored resume and withdrew from Saved, and the database rows matched; the locked state could not be reached because my dev database already has a base resume.

**Feature 13, seed data.** All 29 new tests passed on the first full run, which proved little, so Claude measured the plan against the Insights screenshot with a throwaway script. That showed the v2 prompt had no flagged drafts at all, so "fewer flags than v1" passed only because zero is below anything, and the v1 edit ratios were too high; the flag chances and edit targets were tuned until the edited-only ratios matched the screenshot (32% and 13%). The spec says "a few" flagged resumes, so the flags per draft stay below the screenshot's 1.8 and 0.4: the spec wins. When I ran `make seed ARGS=--reset` it failed with `column applications.posting_tsv does not exist`, the third time my dev database was behind on migrations (features 10 and 11 were the same slip); `alembic upgrade head` fixed it, and because the seed runs in one transaction the failure rolled the truncate back and my 6 applications were still there. The independent review passed with three minor findings and three nits, and I chose to skip all of them, among them an ordering assertion in the history test that can never fail and no test that a failed `--reset` keeps the old data.

**Feature 12, example retrieval.** All 60 new backend tests passed on the first run, which made me suspicious, so I broke the ranking, the tailored-resume filter and the OR join one at a time and checked that each break failed the tests that name it (the snapshot filter failed three, one of them through the API). An older test that said `posting_tsv` must not exist had to change, the same pattern as in feature 11. I asked whether the search was deterministic; it is, because the plan already broke ties by approval date and then id, and a test now pins that order. I also asked what a better design would be, and kept full-text search for the MVP, writing embedding and hybrid search into the overview as later work. With no model key the browser check used sample rows loaded by SQL; once I gave Claude a key, two real calls (the endpoint and the Tailor again button) logged example ids `[3, 2]` in rank order and the draft added no keyword the base resume lacks. The independent review passed with three minor findings and two nits, and I chose to skip all of them: no test that a retrieval error fails the request, the prompt notice lives in `services/` where an edit would not bump the version, an example whose application has no approved analysis gets an empty keyword label, the screenshots are left untracked, and `posting_tsv` is typed as `str`. One slip: a first mutation run used the shared default test database instead of the feature one.

**Feature 14, metrics endpoints.** I asked what the endpoints could write, and Claude searched the code for write calls and confirmed there are none; a test also checks that the row counts don't change after both calls. Checked against `make seed` in a scratch database, the endpoints match the seed's path table exactly but not the Insights screenshot (15, 10 and 20 vs 14, 8 and 19), so the screenshot numbers are illustrative. The independent review passed with four minor findings and two nits. The sixth finding was this log entry, and I chose to skip the other five: the draft ordering has a daylight-saving flaw, there is no database test for posting-analysis counts, the snapshot test would pass without the tailored filter, `_compare_resumes()` loads each call's JSON, and the routes rely on FastAPI converting dataclasses.

**Feature 15, insights page.** The independent review found that the 14-column AI table could stretch the whole page on a phone, because a plain grid column is as wide as its content; my scroll test only checked the `overflow-x-auto` class that the shadcn table always has, so it passed either way. The grids now use `minmax(0,1fr)`, the test checks those classes, and a 375px check in the browser showed only the table scrolling, though I never reproduced the overflow before the fix. The browser check on the seeded data matched the API numbers, and hovering a bar showed I had passed `hideLabel`, so the tooltip never said which stage, against the spec's "default tooltips"; I removed it. Where the page differs from the screenshot on purpose: the Model and Superseded columns, the longer note, dark bars instead of blue, and labels that follow each bar instead of lining up in a column. The independent review passed with one major finding, which I fixed, and five minor ones and nits, which I chose to skip: a failed refetch swaps a section to an error while the tiles keep their numbers, no test for the tiles' loading or error state, the label column, a two-branch `featureLabel()`, and long lines.

**Feature 16, prompt eval.** My first real run passed only 1 of 4 fixtures, although the model invented nothing: the spec's rule "coverage must rise" fails honest drafts, because a draft can only gain a keyword that the base resume lacks word for word, and the guardrail flags exactly that. A second run of one fixture passed with the same prompt, so a single run is noisy. I asked what "coverage" and "base" meant and saw that the flagged words (`automated testing`, `data modeling`) were concepts, not tools, so I chose "coverage not lower than base" and had the spec, overview and goals changed to match. Stemming and aliases went into the overview as later work, and a prompt v2 with tech-only keywords is the planned next step, not built.

<!-- DRAFT by Claude from the feature 17 session. Needs the author's review: it is written in the author's voice. -->

**Feature 17, README, workflow write-up and prompt v2.** Before building I asked whether the app ran v1 or v2 and found the version is fixed by two imports, so a v2 prompt would have changed nothing until someone edited one. v2 is now its own module that only the eval can select, with an architecture test that fails if `app/` uses it. When I asked whether the eval was worth it, I narrowed v2 to the tailoring prompt, so each comparison has one change.

## Prompt iteration

<!-- DRAFT by Claude from the committed results and the six runs of feature 17. Needs the author's review. -->

**What was compared.** `tailor_resume` v1 (what the app runs) against `tailor_resume` v2, on the four fixtures, with the analysis prompt at v1 in both so only tailoring changes. The model was `claude-sonnet-5-5`, which has no temperature setting, so I ran each version three times, interleaved (v1, v2, v1, v2, v1, v2) within about three minutes. The last run of each is committed in `backend/evals/results/`, named `posting_analysis-v1_tailor_resume-v1_...` and `..._tailor_resume-v2_...`. Each run cost about $0.056.

**Why v2.** Both earlier v1 runs (00:13 and 03:11 on 2026-11-20) failed `frontend-react` on "coverage dropped" (59% to 55%, then 57% to 52%), and the trap fixture drew five keyword flags on concepts such as `data modeling` and `data quality`. v2 keeps v1's rules and its inputs and adds three sentences: keep every base-resume term that matches a keyword when rewording, use a keyword's exact words only where the base resume uses them, and do not work out numbers such as years of experience.

**Results.** Each cell lists the three runs in order.

| Fixture | v1 pass | v1 flags | v1 coverage base to draft | v2 pass | v2 flags | v2 coverage base to draft |
| --- | --- | --- | --- | --- | --- | --- |
| `already-covered` | 3 of 3 | 2, 0, 0 | 60 to 80, 60 to 60, 60 to 60 | 3 of 3 | 1, 0, 0 | 60 to 70, 60 to 60, 64 to 64 |
| `backend-python-clean` | 3 of 3 | 0, 0, 3 | 41 to 41, 41 to 41, 39 to 52 | 3 of 3 | 0, 0, 0 | 41 to 41, 41 to 41, 36 to 36 |
| `data-engineer-trap` | 3 of 3 | 2, 5, 5 | 26 to 35, 23 to 45, 23 to 45 | 3 of 3 | 0, 2, 2 | 20 to 20, 25 to 33, 24 to 33 |
| `frontend-react` | 0 of 3 | 0, 0, 0 | 59 to 55, 54 to 50, 59 to 55 | 0 of 3 | 0, 0, 0 | 57 to 52, 57 to 52, 56 to 52 |
| **Total flags per run** | | 4, 5, 8 | | | 1, 2, 2 | |

In all 24 fixture runs there was no employer, title, date or number flag, no skill flag and no forbidden skill in the draft. Every flag in the table is a keyword flag. Both versions pass 3 of 4 fixtures in every run.

**What it shows.**

- **v2 did not fix what it was written for.** `frontend-react` still fails every run, 5 of 5 times under v1 counting the two earlier runs, and 3 of 3 under v2. One extra diagnostic call (not stored) showed the lost keyword is `accessibility`, which the base resume states only in its Summary line, and the draft rewrote the summary without it. v2's rule says a kept term stays "in the skills or in a bullet", so it never mentions the summary. That is a likely cause from one sample, not a proven one.
- **v2 does produce fewer keyword flags** (1, 2, 2 against 4, 5, 8), but it also gains less coverage (the trap fixture reaches at most 33% where v1 reaches 45%). That is the trade-off the overview already describes: a draft can only gain a keyword the base resume lacks word for word by using that word, and the guardrail flags it. Fewer flags here means closer to the base resume, not more honest: v1 invented nothing either.
- **A single run is noisy.** The base coverage of one fixture differs between runs (the trap fixture's from 20% to 26%) because the analysis step returns a slightly different keyword list each time, and v1's flags on one fixture went 0, 0, 3. Compare per fixture on flags and pass or fail, and read the coverage figures within a run, not across runs. Four fixtures and three runs can only show a large effect.

**Decision.** The app stays on v1. v2 is kept, written and measured, and `make eval ARGS=--prompts=v2` reruns it. Switching the app to it would be a one-line change to the default in `tailor()` and a new decision after this write-up is reviewed. I did not tune v2 until it passed.

## Design decisions

<!-- DRAFT by Claude from docs/architecture.md (Key decisions). Needs the author's review. -->

The one idea behind most of the design: let the model do only what code cannot, and follow every model step with a check that code can make and a person who decides. `docs/architecture.md` has the full table; the decisions that mattered most:

- **Only two steps call the model** (extract keywords, write a tailored resume), and only when I click. Everything else, including every metric, is plain code that can be unit tested and gives the same answer every time.
- **The guardrail is code, not a second model call.** The tailored draft is structured data (employer, title, dates, bullets, skills), so code can compare each field with the base resume exactly. Free Markdown could not be checked that reliably. A flag does not block approval and is not auto-fixed: the person decides.
- **Stage rules are data.** Transitions and guards are tables in code, and `change_stage()` is the only writer of `applications.stage`, so the rules are readable in one place and cannot be bypassed by a stray query. An architecture test checks it.
- **Logs are append-only, and the database enforces it.** `timeline_events` and `ai_calls` have triggers that reject UPDATE and DELETE, and `resumes.draft_markdown` cannot change after insert. A convention can be broken by one mistaken query; a trigger cannot.
- **Metrics are calculated, never stored.** A stored counter can drift from the rows it counts; a query cannot. The edit ratio and the outcome of a draft are derived the same way.
- **The call log goes through a sink.** The same code writes `ai_calls` in the app and an in-memory list in the eval, so the eval never needs a database.
- **What was sent is frozen.** Applying with the base resume stores a copy, because the base resume stays editable.

## What I would do next

<!-- DRAFT by Claude from the eval results and the overview's "later improvement" notes. Needs the author's review. -->

In the order I would do them:

1. **Fix the keyword matching before changing prompts again.** The eval's two persistent oddities, keyword flags on honest rewording and a coverage gain that is also a flag, come from literal matching. Stem both sides with one shared normalizer (`monitored` matches `monitoring`), then a small reviewed alias list (`automated testing` with `pytest`). Stemming needs a library, so it needs approval. Earlier results files would no longer be comparable, so each version has to be run again.
2. **A v3 tailoring prompt that names the summary.** v2's rule covers skills and bullets and `frontend-react` still loses `accessibility` from the summary. Try it only after the matching fix, and judge it on that fixture and on flags.
3. **A bigger eval.** Four fixtures and three runs cannot show a small effect. More fixtures, five or more runs per version, and a median per fixture. The eval also runs with retrieval off, so it has never measured whether past examples help; it would need to before building embedding or hybrid search.
4. **Switch the app to a better prompt on evidence** (a one-line default in `tailor()`), and then drop the fictional `v2` rows from the seed data, which today show a `v2` that never ran.

Known limits accepted at the doc review (revisit after the MVP):

- Editing the posting text does not invalidate an existing analysis.
- No delete and no undo of a terminal stage.
- The tailored vs base response rate is confounded, since tailoring may go to better-fit jobs.
- Full-text retrieval drops punctuation (`c++` becomes `c`) and does not stem synonyms.
- Keyword coverage matches exact terms only, so `k8s` and `kubernetes` count as different keywords.
- A call with `max_tokens` above about 21,333 makes the Anthropic SDK raise a plain `ValueError` before anything is sent, so no `ai_calls` row is written and no `AIError` is raised. The default is 8192 and a one-page resume is far below it. Revisit in feature 8 if tailoring needs a higher limit (reasoning tokens count against `max_tokens`).
- The raw model text is not stored: a successful row logs the validated output, and a validation failure keeps only Pydantic's short excerpt in `ai_calls.error`. Revisit in feature 6, when real prompts produce real failures.
