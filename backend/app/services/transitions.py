"""Allowed stage transitions and guards, defined as data.

A transition is allowed when the target is in TRANSITIONS[current]. A guard is a function
`(context) -> None | GuardFailure` registered in GUARDS under an action: a `(from, to)` stage
pair, or a string for another gated step such as "start_tailoring". GUARDS is empty for now;
features 8 and 11 add the real guards.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.models import Application, Stage

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


@dataclass(frozen=True)
class GuardFailure:
    reason: str


@dataclass(frozen=True)
class GuardContext:
    """What a guard may look at. Related records are added here as features need them."""

    application: Application | None
    extra: Mapping[str, Any] = field(default_factory=dict)


Action = tuple[Stage, Stage] | str
Guard = Callable[[GuardContext], GuardFailure | None]

GUARDS: dict[Action, list[Guard]] = {}


def run_guards(action: Action, context: GuardContext) -> GuardFailure | None:
    """The first failure for `action`, or None when every guard passes."""
    for guard in GUARDS.get(action, []):
        failure = guard(context)
        if failure is not None:
            return failure
    return None
