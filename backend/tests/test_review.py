"""The review lifecycle, as data: draft -> approved or rejected, and nothing else."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.models import ReviewStatus
from app.services.review import REVIEW_TRANSITIONS, NotReviewable, apply_decision

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


@dataclass
class Item:
    status: ReviewStatus
    reviewed_at: datetime | None = None


def test_the_lifecycle_is_a_table_with_one_way_out_of_draft() -> None:
    assert REVIEW_TRANSITIONS == {
        ReviewStatus.DRAFT: {ReviewStatus.APPROVED, ReviewStatus.REJECTED},
    }


@pytest.mark.parametrize("decision", [ReviewStatus.APPROVED, ReviewStatus.REJECTED])
def test_a_draft_takes_the_decision_and_is_stamped_with_the_review_time(
    decision: ReviewStatus,
) -> None:
    item = Item(ReviewStatus.DRAFT)

    apply_decision(item, decision, NOW)

    assert item.status is decision
    assert item.reviewed_at == NOW


@pytest.mark.parametrize("current", [ReviewStatus.APPROVED, ReviewStatus.REJECTED])
@pytest.mark.parametrize("decision", [ReviewStatus.APPROVED, ReviewStatus.REJECTED])
def test_a_decided_item_cannot_be_decided_again(
    current: ReviewStatus, decision: ReviewStatus
) -> None:
    item = Item(current, reviewed_at=NOW)

    with pytest.raises(NotReviewable):
        apply_decision(item, decision, datetime(2026, 12, 1, tzinfo=UTC))

    assert item.status is current
    assert item.reviewed_at == NOW


def test_nothing_can_be_set_back_to_draft() -> None:
    item = Item(ReviewStatus.DRAFT)

    with pytest.raises(NotReviewable):
        apply_decision(item, ReviewStatus.DRAFT, NOW)

    assert item.reviewed_at is None
