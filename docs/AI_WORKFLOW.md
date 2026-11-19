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
