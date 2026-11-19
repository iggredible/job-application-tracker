"""Allowed stage transitions and guards, defined as data.

A transition is allowed when the target is in TRANSITIONS[current]. A guard is a function
`(context) -> None | GuardFailure` registered in GUARDS under an action: a `(from, to)` stage
pair, or a string for another gated step such as "start_tailoring". Feature 8 registers the
tailoring guards; feature 11 adds the guards on Saved -> Applied and marks that transition as one
the user performs through its own action.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.models import Application, PostingAnalysis, Resume, Stage
from app.services.submission import unsubmittable_reason

S = Stage

TRANSITIONS: dict[Stage, frozenset[Stage]] = {
    S.SAVED: frozenset({S.APPLIED, S.WITHDRAWN}),
    S.APPLIED: frozenset({S.SCREENING, S.INTERVIEWING, S.REJECTED, S.WITHDRAWN}),
    S.SCREENING: frozenset({S.INTERVIEWING, S.REJECTED, S.WITHDRAWN}),
    S.INTERVIEWING: frozenset({S.OFFER, S.REJECTED, S.WITHDRAWN}),
    S.OFFER: frozenset({S.ACCEPTED, S.REJECTED, S.WITHDRAWN}),
    S.ACCEPTED: frozenset(),
    S.REJECTED: frozenset(),
    S.WITHDRAWN: frozenset(),
}


def allowed_next(stage: Stage) -> list[Stage]:
    """The stages an application in `stage` may move to, in stage order. Empty when terminal."""
    return [candidate for candidate in Stage if candidate in TRANSITIONS[stage]]


# Transitions the user performs through a dedicated action, not the generic Change stage control,
# with the hint shown beside that control. The transition stays in TRANSITIONS: the dedicated
# action goes through change_stage() like any other move.
DEDICATED_ACTIONS: dict[tuple[Stage, Stage], str] = {
    (S.SAVED, S.APPLIED): "Apply in step 3 below",
}


def allowed_next_for_user(stage: Stage) -> list[Stage]:
    """The stages the Change stage control may offer: `allowed_next` without the transitions
    that have a dedicated action."""
    return [target for target in allowed_next(stage) if (stage, target) not in DEDICATED_ACTIONS]


def stage_change_hint(stage: Stage) -> str | None:
    """What to show beside Change stage when a move from `stage` happens elsewhere."""
    for (source, _), hint in DEDICATED_ACTIONS.items():
        if source is stage:
            return hint
    return None


@dataclass(frozen=True)
class GuardFailure:
    reason: str


@dataclass(frozen=True)
class GuardContext:
    """What a guard may look at. Related records are added here as features need them."""

    application: Application | None
    extra: Mapping[str, Any] = field(default_factory=dict)
    approved_analysis: PostingAnalysis | None = None
    base_resume: Resume | None = None
    # The resume the user picked by id (extra["resume_id"]), when it exists.
    chosen_resume: Resume | None = None


Action = tuple[Stage, Stage] | str
Guard = Callable[[GuardContext], GuardFailure | None]


def require_approved_analysis(context: GuardContext) -> GuardFailure | None:
    if context.approved_analysis is None:
        return GuardFailure("The posting analysis must be approved before tailoring.")
    return None


def require_base_resume(context: GuardContext) -> GuardFailure | None:
    if context.base_resume is None:
        return GuardFailure("Save a base resume before tailoring.")
    return None


def require_choice(context: GuardContext) -> GuardFailure | None:
    if context.extra.get("choice") not in ("base", "tailored"):
        return GuardFailure("Choose the resume you sent.")
    return None


def require_submittable_resume(context: GuardContext) -> GuardFailure | None:
    """The base resume must exist, or the tailored resume must be an approved one of this
    application. The choice is known to be valid: `require_choice` runs first."""
    if context.extra["choice"] == "base":
        if context.base_resume is None:
            return GuardFailure("Save a base resume before applying.")
        return None
    if context.extra.get("resume_id") is None:
        return GuardFailure("Choose which tailored resume you sent.")
    if context.chosen_resume is None or context.application is None:
        return GuardFailure("That tailored resume was not found.")
    reason = unsubmittable_reason(context.chosen_resume, context.application.id)
    return GuardFailure(reason) if reason else None


GUARDS: dict[Action, list[Guard]] = {
    "start_tailoring": [require_approved_analysis, require_base_resume],
    (S.SAVED, S.APPLIED): [require_choice, require_submittable_resume],
}


def run_guards(action: Action, context: GuardContext) -> GuardFailure | None:
    """The first failure for `action`, or None when every guard passes."""
    for guard in GUARDS.get(action, []):
        failure = guard(context)
        if failure is not None:
            return failure
    return None
