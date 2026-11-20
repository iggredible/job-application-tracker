# States

The state machines in the app, drawn as state machine diagrams: every state, the start and terminal states, every allowed transition, and the condition on each. Follow `conventions.md`, except for the diagram rules in "Diagrams" below, which are specific to this action.

The transitions and guards are defined as data (CLAUDE.md), so read them from the code and do not infer them from prose.

## Mode

- No argument: the application stage machine.
- `drafts`: the review lifecycle of AI output (analyses, tailored resumes). See the last section.

Also reachable as `/tour show-states`.

## Facts (run, do not eyeball)

Two commands, both run from `backend/`.

**A. The Mermaid source** (also the input to the diagram, see "Diagrams"). Edges come straight from `TRANSITIONS`, and a transition with guards gets the label `[guarded]`:

```
uv run python -c "
from app.models import Stage
from app.services import transitions as t
print('stateDiagram-v2')
print('    [*] --> Saved : create')
for s in Stage:
    for n in t.allowed_next(s):
        label = ' : [guarded]' if (s, n) in t.GUARDS else ''
        print(f'    {s.name.title()} --> {n.name.title()}{label}')
for s in Stage:
    if not t.TRANSITIONS[s]: print(f'    {s.name.title()} --> [*]')
"
```

**B. The details**: each guard with its line number, the dedicated actions, the effects, and the edge count.

```
uv run python -c "
import inspect
from app.services import transitions as t, applications as a
for k, gs in t.GUARDS.items():
    for g in gs: print('guard', k, g.__name__, inspect.getsourcelines(g)[1])
print('dedicated', t.DEDICATED_ACTIONS)
print('effects', {k: (v.__name__, inspect.getsourcelines(v)[1]) for k, v in a._EFFECTS.items()})
print('edges', sum(len(v) for v in t.TRANSITIONS.values()))
"
```

If either fails, say so and read `backend/app/services/transitions.py` and the `_EFFECTS` table in `backend/app/services/applications.py` directly. Do not make up transitions.

Then read, for the explanation and `file:line` of each item:

- `backend/app/services/transitions.py`: `TRANSITIONS`, `GUARDS`, `DEDICATED_ACTIONS`, each guard function (its docstring and `GuardFailure` reasons are the condition, in the app's own words).
- `backend/app/services/applications.py`: `change_stage()` and each function named in `_EFFECTS`.
- `backend/app/models/application.py`: the default stage. The start state is the column default, not "the state with no incoming edges". Check both agree and say so if they do not.
- Terminal states: the stages whose target set is empty. Cross-check against `docs/project-overview.md`.

## Output

```
Tour states | ...stamp

## Application stages
Start: Saved  (column default, `models/application.py:NN`). Terminal: Accepted, Rejected, Withdrawn  (empty target sets, `services/transitions.py:NN`)

(state machine diagram, see below)

## Transitions
| From | To | Condition | Offered by |
One row per source stage. List targets together when they share a condition (usually "none"). The Condition column is the guard in plain language with `file:line`, or "none". The "Offered by" column says whether the generic Change stage control offers it, or only a dedicated action (`DEDICATED_ACTIONS`).

## Conditions in detail
For each guarded transition: the guards in the order they run (the first failure wins), what each checks, and the reason it returns, each with `file:line`.

## Effects
What a transition does besides moving the stage (`_EFFECTS`): the function, what it does, `file:line`. Say that it runs after the guards, in the same transaction.

## Gated steps (not stage moves)
Entries in `GUARDS` keyed by a string, not a stage pair (for example `start_tailoring`): what they gate and their guards. These do not change `applications.stage`.

## Summary
N states, N transitions, N with a condition, N with an effect. If most transitions have no condition, say so plainly. Do not invent conditions.

## Doc drift          (only if found)
## Things worth knowing   (only if real)
```

### Diagrams

The diagram is rendered in the terminal from the Mermaid source in command A, with termaid. The source comes from the code, so the picture cannot disagree with it.

**1. Render it** (pinned version, run from `backend/`; command A piped in):

```
<command A> | uvx termaid==0.13.0 --padding-y 0 --padding-x 1 --gap 1 --width 100
```

This draws a state machine with `●` for the start, `◉` for terminal states, and arrows with labels. With these flags the stage machine is about 100 columns by 33 lines. termaid is a third-party Python package with no dependencies; `uvx` runs it in a throwaway environment and installs nothing into the project, so it is not a project dependency. Tell the user once, on first use, that the diagram is rendered by `termaid` via `uvx`.

**2. Show it to the user.** Tool output is not reliably visible to the user. Paste the rendered diagram into the reply, unchanged, in a fenced code block. Do not redraw it by hand.

**3. Check it.** Count the edges in the Mermaid source (lines containing `-->`, minus the `[*]` ones) and compare with `edges` from command B. If they differ, say so and print the transitions table only.

**4. Read it for the user.** The routes into Rejected and Withdrawn cross each other, because five states can reach Withdrawn and four can reach Rejected. Right under the diagram, add two lines so nobody has to trace them: "Rejected: from Applied, Screening, Interviewing, Offer." and "Withdrawn: from every non-terminal state." (derived from the data). The transitions table carries the same facts.

**Fallbacks**, in order. Say which one was used and why.

1. `uvx` or termaid fails (no network, not installed): print the Mermaid source in a fenced `mermaid` block, and say it can be pasted into a markdown preview or mermaid.live.
2. Output wider than the terminal (the user says it wraps): rerun with `--width 80`; if it is still too wide, use the fallback above.

Do not use composite states (`state X { ... }`) to shorten the diagram. termaid draws a target inside the group box, which wrongly suggests it belongs to the group.

**`--save`** writes `.tour/states.md` with the stamp, the transitions table, and the Mermaid source in a fenced `mermaid` block (GitHub and editor previews render it). It can be shown in the terminal later with `uvx termaid==0.13.0 --markdown .tour/states.md`; tell the user this command.

**`--mermaid`** also prints the Mermaid source in the reply.

The "about ten nodes" rule is met by the stage machine (8 states). If a diagram would pass about 12, split it.

## `drafts`

The review lifecycle that AI output goes through before a person approves it. CLAUDE.md: every AI output is saved as `draft`; only a user action sets `approved` or `rejected`.

1. Read the status enum (`ReviewStatus` in `backend/app/models/resume.py`, and the one for posting analyses in `backend/app/models/posting_analysis.py`), the review services (`backend/app/services/review.py`, `backend/app/services/resume_review.py`, `backend/app/services/analysis.py`), and the approve and reject endpoints (from the route list, convention 2).
2. Report: the states, the start (`draft`), the terminals (`approved`, `rejected`), each transition with its trigger (the endpoint), and the condition for it (for example can only a draft be approved, what happens on a second approve). Every claim with `file:line`.
3. `superseded` is not a stored state. It is derived from "a newer draft exists for the same application" (`services/resume_review.py`, `services/metrics.py`). Draw it as a note on `draft`, not as a state, and say it is never stored.
4. Say what is editable in each state (for example, whether a draft's content can be edited and when `draft_markdown` is fixed).
5. Write the Mermaid `stateDiagram-v2` by hand from what you read (it is three states, so there is no generator), render it with the same termaid command as under "Diagrams", and apply the same checks, fallbacks and `--save` rules. Add the same Conditions, Doc drift and Summary sections.

Compare with the "Analyses and resumes have their own small lifecycle" paragraph in `docs/architecture.md` and report disagreements.
