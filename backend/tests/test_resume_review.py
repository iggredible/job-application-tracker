"""The two helpers behind the review flow: the outcome and the edit ratio. Both are pure and
calculated on request, never stored."""

import pytest

from app.models import ReviewStatus
from app.services.resume_review import Outcome, derive_outcome, edit_ratio

DRAFT_TEXT = "# Jordan Avery\n\n## Summary\nBackend lead.\n"
EDITED_TEXT = "# Jordan Avery\n\n## Summary\nBackend lead on Rails.\n"


# --- derive_outcome -----------------------------------------------------------------------------


def test_the_outcomes_are_pending_superseded_approved_edited_then_approved_and_rejected() -> None:
    assert {o.value for o in Outcome} == {
        "pending",
        "superseded",
        "approved",
        "edited_then_approved",
        "rejected",
    }


def test_a_draft_with_no_newer_draft_is_pending() -> None:
    outcome = derive_outcome(ReviewStatus.DRAFT, DRAFT_TEXT, DRAFT_TEXT, superseded=False)

    assert outcome is Outcome.PENDING


def test_a_draft_with_a_newer_draft_is_superseded_not_pending() -> None:
    outcome = derive_outcome(ReviewStatus.DRAFT, DRAFT_TEXT, DRAFT_TEXT, superseded=True)

    assert outcome is Outcome.SUPERSEDED


def test_editing_a_draft_does_not_change_whether_it_is_superseded() -> None:
    superseded = derive_outcome(ReviewStatus.DRAFT, DRAFT_TEXT, EDITED_TEXT, superseded=True)
    pending = derive_outcome(ReviewStatus.DRAFT, DRAFT_TEXT, EDITED_TEXT, superseded=False)

    assert superseded is Outcome.SUPERSEDED
    assert pending is Outcome.PENDING


def test_an_approved_resume_with_its_generated_text_is_approved() -> None:
    outcome = derive_outcome(ReviewStatus.APPROVED, DRAFT_TEXT, DRAFT_TEXT, superseded=False)

    assert outcome is Outcome.APPROVED


def test_an_approved_resume_whose_text_was_edited_is_edited_then_approved() -> None:
    outcome = derive_outcome(ReviewStatus.APPROVED, DRAFT_TEXT, EDITED_TEXT, superseded=False)

    assert outcome is Outcome.EDITED_THEN_APPROVED


def test_an_edit_that_was_changed_back_counts_as_unedited() -> None:
    # Edited is "the text differs from the generated text", so undoing every edit is not an edit.
    outcome = derive_outcome(ReviewStatus.APPROVED, DRAFT_TEXT, DRAFT_TEXT, superseded=False)

    assert outcome is Outcome.APPROVED


@pytest.mark.parametrize("content", [DRAFT_TEXT, EDITED_TEXT])
def test_a_rejected_resume_is_rejected_whether_or_not_it_was_edited(content: str) -> None:
    outcome = derive_outcome(ReviewStatus.REJECTED, DRAFT_TEXT, content, superseded=False)

    assert outcome is Outcome.REJECTED


@pytest.mark.parametrize(
    ("status", "outcome"),
    [(ReviewStatus.APPROVED, Outcome.APPROVED), (ReviewStatus.REJECTED, Outcome.REJECTED)],
)
def test_a_newer_draft_never_supersedes_a_decided_resume(
    status: ReviewStatus, outcome: Outcome
) -> None:
    assert derive_outcome(status, DRAFT_TEXT, DRAFT_TEXT, superseded=True) is outcome


# --- edit_ratio ---------------------------------------------------------------------------------


def test_the_edit_ratio_is_zero_for_unedited_text() -> None:
    assert edit_ratio(DRAFT_TEXT, DRAFT_TEXT) == 0.0


def test_the_edit_ratio_is_zero_when_both_texts_are_empty() -> None:
    assert edit_ratio("", "") == 0.0


def test_the_edit_ratio_is_one_for_text_with_nothing_in_common() -> None:
    assert edit_ratio("aaaa", "bbbb") == 1.0


def test_the_edit_ratio_grows_with_the_size_of_the_edit() -> None:
    small = edit_ratio(DRAFT_TEXT, DRAFT_TEXT.replace("lead", "leader"))
    large = edit_ratio(DRAFT_TEXT, "# Someone Else\n\n## Summary\nFrontend designer.\n")

    assert 0.0 < small < large < 1.0


def test_the_edit_ratio_is_one_minus_the_sequence_matcher_ratio() -> None:
    from difflib import SequenceMatcher

    expected = 1 - SequenceMatcher(None, DRAFT_TEXT, EDITED_TEXT, autojunk=False).ratio()

    assert edit_ratio(DRAFT_TEXT, EDITED_TEXT) == pytest.approx(expected)


def test_the_edit_ratio_is_exact_on_text_longer_than_200_characters() -> None:
    # Over 200 characters, difflib's default autojunk would treat the common characters as
    # noise and report 1.0 for this swap of two blocks. With autojunk off the answer is 1/3.
    draft = "a" * 100 + "b" * 100 + "c" * 100
    content = "c" * 100 + "a" * 100 + "b" * 100
    assert len(draft) > 200

    assert edit_ratio(draft, content) == pytest.approx(1 / 3)
