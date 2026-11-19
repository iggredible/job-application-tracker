"""The one stale rule. Everything that says "stale" calls this."""

from datetime import datetime

from app.models import Stage
from app.services.transitions import allowed_next

STALE_AFTER_DAYS = 14


def idle_days(last_activity_at: datetime, now: datetime) -> int:
    """Whole days since the last activity, rounded down."""
    return max(0, (now - last_activity_at).days)


def is_stale(stage: Stage, last_activity_at: datetime, now: datetime) -> bool:
    """Stale: the stage is not terminal and the last activity is 14 or more days old."""
    is_terminal = not allowed_next(stage)
    return not is_terminal and idle_days(last_activity_at, now) >= STALE_AFTER_DAYS
