# Frontend

An inventory of the React app with the explanation the user is missing. Follow `conventions.md`.

## Scope

All under `frontend/src/`:

- `pages/`: route-level screens (`*Page.tsx`). Skip `*.test.tsx`.
- `components/`: feature components shared across pages.
- `components/<feature>/`: components for one page (for example `insights/`).
- `components/ui/`: shadcn primitives. Names and a count only.
- `hooks/` and `lib/`: read only to say what a component calls.

Skip `main.tsx`, `test-utils.tsx` and tests, except `routes.tsx`, which supplies the route table.

## Mode

- No argument: overview.
- A subdirectory (`pages`, `insights`, `ui`): overview of just that folder.
- A component, page or hook name (case-insensitive): deep dive. If nothing matches, say so and list the closest names. If several match, list them and stop.

## Overview

Map in a subagent (convention 4):

1. `Glob` the in-scope `.tsx` files; `Read` each non-`ui/` component.
2. Find where each is used: `Grep` for `import .*<Name>` and `<Name` and count real call sites, not the definition.
3. Build the **API map**: for each helper in `lib/` that calls the backend, the endpoint it calls (`METHOD /path`) and the hook that wraps it. This is what connects the frontend to the backend, so it matters more than the component details.

### Output

```
Tour frontend | ...stamp

## Pages and routes
| URL | Page | Composes |

## Component tree
(one tree diagram of the page -> component composition, about ten nodes; split per page if larger)

## Components
### StageBadge  (`components/StageBadge.tsx:NN`)
What it does: one sentence, from the user's point of view.
Props: `stage: Stage` (or none)
Data: hooks or helpers it calls (or "none, presentational")
Used by: `ApplicationDetailPage:NN`, ... (or "unused")

## UI primitives
shadcn: card, dialog, ... (N)

## API map
| Hook | lib helper | Endpoint |

## Counts
pages N, feature components N, ui primitives N, hooks N

## Doc drift          (only if found)
## Things worth knowing   (only if real)
```

Group components by layer: shared first, then each feature folder. Keep each description to one sentence in the overview.

"Things worth knowing" examples: an unused component, two components doing nearly the same job, a component that calls the API directly and not through a hook, and anything that looks like a business rule. CLAUDE.md says the frontend renders what the API returns and holds no business rules, so flag candidates with `file:line` and say why they look like rules. Check the doc drift against the "Frontend" section of `docs/architecture.md`.

## Deep dive

Read the component or hook directly, and its tests (`Grep` the test files for its name). Report:

1. **Purpose** in two sentences.
2. **Props**, and what each is for.
3. **Behavior**: states it can show (loading, empty, error, populated), user actions it handles, and what each action calls (down to the endpoint, through the hook and `lib/` helper).
4. **Depends on**: shadcn primitives, hooks, helpers, child components.
5. **Used by**, and where it sits on the page.
6. **Tests**: test file and the behaviors it asserts, or "no direct test".
7. **Where to look first** if the user wants to change it.
