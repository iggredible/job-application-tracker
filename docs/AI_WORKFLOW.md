# AI Workflow

How this app was built from a written specification using Claude Code.

## Approach

<!-- Spec first, then plan, then build, one feature per session. Which documents drove the work. -->

## How I verified the work

<!-- What was read line by line, what was trusted to tests, what was checked by hand. -->

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

## Prompt iteration

<!-- Eval results for prompt v1 and v2, and what changed between them. -->

## Design decisions

<!-- Deterministic vs non-deterministic split, guards, append-only logs, and why. -->

## What I would do next

<!-- Honest gaps and what more time would add. -->

Known limits accepted at the doc review (revisit after the MVP):

- Editing the posting text does not invalidate an existing analysis.
- No delete and no undo of a terminal stage.
- The tailored vs base response rate is confounded, since tailoring may go to better-fit jobs.
- Full-text retrieval drops punctuation (`c++` becomes `c`) and does not stem synonyms.
- Keyword coverage matches exact terms only, so `k8s` and `kubernetes` count as different keywords.
- A call with `max_tokens` above about 21,333 makes the Anthropic SDK raise a plain `ValueError` before anything is sent, so no `ai_calls` row is written and no `AIError` is raised. The default is 8192 and a one-page resume is far below it. Revisit in feature 8 if tailoring needs a higher limit (reasoning tokens count against `max_tokens`).
- The raw model text is not stored: a successful row logs the validated output, and a validation failure keeps only Pydantic's short excerpt in `ai_calls.error`. Revisit in feature 6, when real prompts produce real failures.
