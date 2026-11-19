"""The review lifecycle, as data. A draft is approved or rejected by a user, and that is final.

Only `apply_decision()` sets a status on an AI output, so the rule lives in one place. Posting
analyses use it now, and tailored resumes will (feature 10).
"""

from datetime import datetime
from typing import Protocol

from app.models import ReviewStatus

# From each status, the statuses a user decision may move it to. Approved and rejected are final.
REVIEW_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.DRAFT: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
}


class NotReviewable(Exception):
    """The decision is not allowed from the item's current status."""


class Reviewable(Protocol):
    status: ReviewStatus
    reviewed_at: datetime | None


def apply_decision(item: Reviewable, decision: ReviewStatus, now: datetime) -> None:
    """Set the status and the review time, or raise NotReviewable and change nothing."""
    if decision not in REVIEW_TRANSITIONS.get(item.status, set()):
        raise NotReviewable(f"cannot go from {item.status.value} to {decision.value}")
    item.status = decision
    item.reviewed_at = now
