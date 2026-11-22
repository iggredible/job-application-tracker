# Demo

A walk through the app, from an empty machine to the Insights page. It takes about ten minutes and costs a few cents of model calls (the run this page was checked on cost about $0.03).

Every step here was run on a fresh clone, with its own databases, against the real model, and the pages were compared with `docs/screenshots/`. What you see will differ in small ways: the model's wording and keywords change from run to run, and the seed's dates are counted back from today.

## 1. Set up

You need Python 3.12, uv, Node and a local PostgreSQL 16 (see the README).

```bash
make setup     # creates the dev and test databases, runs the migrations, installs the dependencies
```

`make setup` creates `.env` from `.env.example`. Put `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in it. Steps 4 to 6 call the model and need both. Without them the app starts and everything else works; Analyze and Tailor resume answer "AI is not configured."

```bash
make seed      # about 40 fictional applications, timelines, analyses and drafts (no AI calls)
make dev       # the API on :8000 and the web app on :5173
```

Open <http://localhost:5173>. The API docs are at <http://localhost:8000/docs>.

## 2. The list

You see 40 applications, a count per stage (Saved 4, Applied 11, Screening 1, Interviewing 4, Offer 1, Accepted 1, Rejected 11, Withdrawn 7), a notice that 5 have had no recent activity, and a table with the stage, which resume was sent and the last activity, with a **Stale** tag on the five. Click a stage to filter. The data comes from a fixed seed, so these numbers are the same every time.

## 3. Open an application with nothing done yet

Click **Cobaltine Labs**, Senior Data Engineer (Saved, the seventh row). The step strip shows step 1, Posting analysis, as current. Step 2 is locked ("Locked until the analysis is approved") and the Tailored resume section is dashed with its button disabled. This is the guard: tailoring needs an approved analysis.

## 4. Analyze the posting

Click **Analyze**. After a few seconds the Posting analysis card shows a **Draft** badge and "Prompt v1", the requirements as a must-have list, the keywords, and keyword coverage of the base resume: in the checked run, 47% (7 of 15), with the covered and the missing keywords listed. Nothing uses the analysis yet. Check it against the posting on the left, then click **Approve**. Step 1 turns green and the Tailored resume section unlocks.

## 5. Tailor the resume and read the guardrail

Click **Tailor resume**. When the draft arrives you see:

- a **Draft** badge, "Prompt v1" and "3 past examples used". Retrieval found up to three approved resumes among the seeded ones, and their ids are logged on the call.
- a yellow box listing what the draft contains that the base resume does not. In the checked run it was one thing, Keyword "monitoring". This is the deterministic guardrail: the model's output is compared with the base resume, and employers, titles, dates, numbers, skills and posting keywords that are not there are flagged. A flag never blocks approval and is never fixed for you.
- the base resume (read-only) and the draft (editable) side by side, and the coverage line, here 47% to 53%.

You can edit the draft and click **Save edits**; the flags and coverage are recalculated from the text, so removing a flagged word clears its flag. Click **Approve**. The draft becomes read-only and **Copy Markdown** appears.

## 6. Mark as applied

In the Mark as applied section choose **Tailored resume** and click **Mark as applied**. The stage becomes Applied, the timeline gets a Saved to Applied entry, the step strip turns all green ("Resume sent") and the section is replaced by "Applied Nov 19 with the tailored resume". Back on the list the application shows Applied and "Tailored".

Choosing **Base resume** instead saves a frozen copy of it for this application, so editing the base resume later never changes what was sent.

To see the log behind the screens:

```bash
psql job_tracker -c "select feature, prompt_version, model, schema_valid, retrieved_example_ids from ai_calls order by id desc limit 2"
psql job_tracker -c "select type, from_stage, to_stage from timeline_events where application_id = 34 order by id"
```

## 7. Insights

Open **Insights**. The Applied tile has gone up by one, and the AI performance table now has separate rows for your two real calls (model `claude-sonnet-5-5`, prompt `v1`, one call each, with their cost and latency, and a flag count of 1.0 for the tailored draft) next to the seeded rows (model `seed`). Every number is calculated from `timeline_events` and `ai_calls` when the page loads; nothing is stored.

The seeded rows include a `v2` prompt that never ran. It exists to make the table readable. The real `v2` tailoring prompt is only used by the eval (see `docs/AI_WORKFLOW.md`).

## 8. Two more pages

- **Resume** shows the base resume editor, with the note on how it is used. Every tailored resume is written from it.
- **New application** on the list opens the dialog for a new application. Editing an application on its detail page uses the same dialog.

## If you have no API key

Skip steps 4 and 5. **Inkwell Games** (Platform Engineer, Saved) already has an approved analysis and an approved tailored resume from the seed, so its step 3 is ready: go straight to step 6. (I checked this state through the API, not in the browser.)

## Differences from the screenshots

The pages were compared one by one with `docs/screenshots/`. Where they differ, the spec or the UI rules win over the screenshot (`CLAUDE.md`).

| Page | Difference | Why |
| --- | --- | --- |
| All | Sample data: 40 applications and Riley Hartwell's resume here, 10 applications and Jordan Avery's in the screenshots; the numbers on Insights differ too | The screenshots are illustrations, and the seed was shaped to match them in outline only |
| List | No "N in progress" in the subtitle; stage badges are plain shadcn variants and not coloured pills; column headings are not upper case | Spec 2 asks for the count only, and the UI rules say shadcn defaults with no custom design |
| List | The notice says "no recent activity" and not "14 or more days" | The API does not send the threshold, so the frontend would have copied a business rule (feature 3) |
| New application dialog | Opens empty, the subtitle is shorter ("It will be saved in the Saved stage.") and the backdrop is blurred | The screenshot shows a filled-in example |
| Detail (all three states) | No "All applications" link above the title; Analyze again sits at the bottom of the analysis card, not top right; the Approved badge is dark and not green | The back link is in no spec, and you go back with the Applications tab; the badge was left open in feature 10 |
| Detail, step 2 and 3 | No "Read-only now that it is approved" note; the Mark as applied options show no coverage figure and none is pre-selected | The note was left open in feature 10; the others are in no spec |
| Insights | Model and Superseded columns, dark bars, labels beside the bars, a longer note under the resume comparison | Recorded in feature 15 |
| Base resume | None in layout | |

(None of the pages logged a console error or warning during the walk)
