"""The pure rules of feature 11: the three workflow steps, which resumes may be sent, and the
guards and hint that keep Saved -> Applied behind the apply action. No database."""

from itertools import product

import pytest

from app.models import Application, Resume, ReviewStatus, Stage
from app.services.submission import (
    StepKey,
    StepStatus,
    unsubmittable_reason,
    workflow_steps,
)
from app.services.transitions import (
    DEDICATED_ACTIONS,
    GUARDS,
    GuardContext,
    GuardFailure,
    allowed_next,
    allowed_next_for_user,
    run_guards,
    stage_change_hint,
)

S = Stage
R = ReviewStatus
DONE, SKIPPED, LOCKED = StepStatus.DONE, StepStatus.SKIPPED, StepStatus.LOCKED
CURRENT, AVAILABLE = StepStatus.CURRENT, StepStatus.AVAILABLE


def steps(
    stage: Stage = S.SAVED,
    analyses: list[ReviewStatus] | None = None,
    tailored: list[ReviewStatus] | None = None,
    base: bool = True,
    submitted: bool = False,
) -> dict[StepKey, StepStatus]:
    result = workflow_steps(
        stage=stage,
        analysis_statuses=analyses or [],
        tailored_statuses=tailored or [],
        has_base_resume=base,
        has_submitted_resume=submitted,
    )
    return {step.key: step.status for step in result}


def all_three(
    first: StepStatus, second: StepStatus, third: StepStatus
) -> dict[StepKey, StepStatus]:
    return {StepKey.ANALYSIS: first, StepKey.TAILORED: second, StepKey.APPLY: third}


# --- step 1: posting analysis -------------------------------------------------------------------


def test_step_1_is_current_for_a_new_application() -> None:
    assert steps()[StepKey.ANALYSIS] is CURRENT


@pytest.mark.parametrize("analyses", [[R.DRAFT], [R.REJECTED], [R.DRAFT, R.REJECTED]])
def test_step_1_is_current_until_an_analysis_is_approved(analyses: list[R]) -> None:
    assert steps(analyses=analyses)[StepKey.ANALYSIS] is CURRENT


@pytest.mark.parametrize(
    "analyses", [[R.APPROVED], [R.DRAFT, R.APPROVED], [R.REJECTED, R.APPROVED]]
)
def test_step_1_is_done_when_an_analysis_is_approved(analyses: list[R]) -> None:
    assert steps(analyses=analyses)[StepKey.ANALYSIS] is DONE


@pytest.mark.parametrize("stage", [s for s in Stage if s is not S.SAVED])
def test_step_1_is_skipped_when_the_application_left_saved_without_one(stage: Stage) -> None:
    assert steps(stage=stage, analyses=[R.DRAFT, R.REJECTED])[StepKey.ANALYSIS] is SKIPPED
    assert steps(stage=stage)[StepKey.ANALYSIS] is SKIPPED


def test_step_1_stays_done_after_the_application_left_saved() -> None:
    assert steps(stage=S.APPLIED, analyses=[R.APPROVED])[StepKey.ANALYSIS] is DONE


# --- step 2: tailored resume --------------------------------------------------------------------


def test_step_2_is_locked_without_an_approved_analysis() -> None:
    assert steps(analyses=[R.DRAFT])[StepKey.TAILORED] is LOCKED
    assert steps(tailored=[R.APPROVED])[StepKey.TAILORED] is DONE  # done is checked before locked


def test_step_2_is_current_once_the_analysis_is_approved() -> None:
    assert steps(analyses=[R.APPROVED])[StepKey.TAILORED] is CURRENT
    assert steps(analyses=[R.APPROVED], tailored=[R.DRAFT])[StepKey.TAILORED] is CURRENT
    assert steps(analyses=[R.APPROVED], tailored=[R.REJECTED])[StepKey.TAILORED] is CURRENT


def test_step_2_is_done_when_a_tailored_resume_is_approved() -> None:
    result = steps(analyses=[R.APPROVED], tailored=[R.DRAFT, R.APPROVED])

    assert result[StepKey.TAILORED] is DONE


@pytest.mark.parametrize("stage", [s for s in Stage if s is not S.SAVED])
def test_step_2_is_skipped_when_the_application_left_saved_without_one(stage: Stage) -> None:
    assert (
        steps(stage=stage, analyses=[R.APPROVED], tailored=[R.DRAFT])[StepKey.TAILORED] is SKIPPED
    )


def test_step_2_only_counts_tailored_resumes() -> None:
    # The caller passes tailored resumes only. A base snapshot has no AI call, so it is never in
    # the list and an application that sent the base resume has skipped step 2.
    result = steps(stage=S.APPLIED, analyses=[R.APPROVED], tailored=[], submitted=True)

    assert result[StepKey.TAILORED] is SKIPPED


# --- step 3: mark as applied --------------------------------------------------------------------


def test_step_3_is_done_when_the_application_left_saved_with_a_submitted_resume() -> None:
    assert steps(stage=S.APPLIED, submitted=True)[StepKey.APPLY] is DONE
    assert steps(stage=S.INTERVIEWING, submitted=True)[StepKey.APPLY] is DONE


@pytest.mark.parametrize("base", [True, False])
def test_step_3_is_skipped_never_done_for_an_application_withdrawn_from_saved(base: bool) -> None:
    result = steps(stage=S.WITHDRAWN, analyses=[R.APPROVED], tailored=[R.APPROVED], base=base)

    assert result[StepKey.APPLY] is SKIPPED


def test_an_application_withdrawn_from_saved_shows_what_was_done_and_skips_the_rest() -> None:
    result = steps(stage=S.WITHDRAWN, analyses=[R.APPROVED])

    assert result == all_three(DONE, SKIPPED, SKIPPED)


def test_step_3_is_locked_without_a_base_resume() -> None:
    assert steps(base=False)[StepKey.APPLY] is LOCKED
    assert steps(base=False, analyses=[R.APPROVED], tailored=[R.APPROVED])[StepKey.APPLY] is LOCKED


def test_step_3_is_current_when_a_tailored_resume_is_approved_and_the_stage_is_saved() -> None:
    result = steps(analyses=[R.APPROVED], tailored=[R.APPROVED])

    assert result == all_three(DONE, DONE, CURRENT)


def test_step_3_is_available_otherwise() -> None:
    assert steps()[StepKey.APPLY] is AVAILABLE
    assert steps(analyses=[R.APPROVED], tailored=[R.DRAFT])[StepKey.APPLY] is AVAILABLE


def test_a_new_application_with_a_base_resume() -> None:
    assert steps() == all_three(CURRENT, LOCKED, AVAILABLE)


def test_the_third_step_does_not_hide_behind_an_unfinished_second() -> None:
    result = steps(analyses=[R.APPROVED], tailored=[R.DRAFT])

    assert result == all_three(DONE, CURRENT, AVAILABLE)


def test_at_most_one_step_is_current_in_every_combination() -> None:
    statuses = [[], [R.DRAFT], [R.REJECTED], [R.APPROVED], [R.DRAFT, R.APPROVED]]
    for stage, analyses, tailored, base, submitted in product(
        Stage, statuses, statuses, [True, False], [True, False]
    ):
        if tailored and R.APPROVED not in analyses:
            continue  # unreachable: tailoring needs an approved analysis, which stays approved
        result = workflow_steps(
            stage=stage,
            analysis_statuses=analyses,
            tailored_statuses=tailored,
            has_base_resume=base,
            has_submitted_resume=submitted,
        )
        current = [step for step in result if step.status is CURRENT]
        assert len(current) <= 1, (stage, analyses, tailored, base, submitted)
        assert [step.key for step in result] == [StepKey.ANALYSIS, StepKey.TAILORED, StepKey.APPLY]


def test_every_step_has_a_line_of_text() -> None:
    result = workflow_steps(
        stage=S.SAVED,
        analysis_statuses=[R.DRAFT],
        tailored_statuses=[],
        has_base_resume=True,
        has_submitted_resume=False,
    )

    assert [step.text for step in result] == [
        "Draft waiting for your review",
        "Locked until the analysis is approved",
        "Pick the resume you sent",
    ]


# --- which resumes may be sent ------------------------------------------------------------------


def tailored_resume(status: ReviewStatus, application_id: int = 1, ai_call_id: int | None = 7):
    return Resume(application_id=application_id, ai_call_id=ai_call_id, status=status)


def test_an_approved_tailored_resume_of_this_application_may_be_sent() -> None:
    assert unsubmittable_reason(tailored_resume(R.APPROVED), 1) is None


def test_a_draft_may_not_be_sent() -> None:
    assert unsubmittable_reason(tailored_resume(R.DRAFT), 1) == "Approve this draft first"


def test_a_rejected_resume_may_not_be_sent() -> None:
    assert unsubmittable_reason(tailored_resume(R.REJECTED), 1) == "This draft was rejected"


def test_another_applications_resume_may_not_be_sent() -> None:
    reason = unsubmittable_reason(tailored_resume(R.APPROVED, application_id=2), 1)

    assert reason == "That resume belongs to another application"


@pytest.mark.parametrize("application_id", [1, None])
def test_a_base_resume_snapshot_or_the_base_row_is_not_a_tailored_resume(
    application_id: int | None,
) -> None:
    # A snapshot has an application but no AI call. The base row has neither.
    resume = tailored_resume(R.APPROVED, application_id=application_id, ai_call_id=None)  # type: ignore[arg-type]

    assert unsubmittable_reason(resume, 1) == "That is not a tailored resume"


# --- the guards and the hint, as data -----------------------------------------------------------


def apply_context(**extra: object) -> GuardContext:
    return GuardContext(
        application=Application(id=1),
        extra=extra,
        base_resume=Resume(application_id=None, status=R.APPROVED),
    )


def test_the_saved_to_applied_guards_are_registered_as_data() -> None:
    assert len(GUARDS[(S.SAVED, S.APPLIED)]) == 2


def test_the_guard_requires_a_choice() -> None:
    failure = run_guards((S.SAVED, S.APPLIED), apply_context())

    assert isinstance(failure, GuardFailure)
    assert failure.reason == "Choose the resume you sent."


def test_the_guard_accepts_the_base_resume_when_one_exists() -> None:
    assert run_guards((S.SAVED, S.APPLIED), apply_context(choice="base")) is None


def test_the_guard_refuses_the_base_choice_without_a_base_resume() -> None:
    context = GuardContext(application=Application(id=1), extra={"choice": "base"})

    failure = run_guards((S.SAVED, S.APPLIED), context)

    assert failure == GuardFailure("Save a base resume before applying.")


def test_the_guard_needs_a_resume_id_for_a_tailored_choice() -> None:
    failure = run_guards((S.SAVED, S.APPLIED), apply_context(choice="tailored"))

    assert failure == GuardFailure("Choose which tailored resume you sent.")


def test_the_guard_refuses_a_tailored_choice_that_was_not_found() -> None:
    failure = run_guards((S.SAVED, S.APPLIED), apply_context(choice="tailored", resume_id=9))

    assert failure == GuardFailure("That tailored resume was not found.")


def test_the_guard_applies_the_submittable_rule_to_a_tailored_choice() -> None:
    context = GuardContext(
        application=Application(id=1),
        extra={"choice": "tailored", "resume_id": 5},
        chosen_resume=tailored_resume(R.DRAFT),
    )

    assert run_guards((S.SAVED, S.APPLIED), context) == GuardFailure("Approve this draft first")


def test_the_guard_accepts_an_approved_tailored_choice() -> None:
    context = GuardContext(
        application=Application(id=1),
        extra={"choice": "tailored", "resume_id": 5},
        chosen_resume=tailored_resume(R.APPROVED),
    )

    assert run_guards((S.SAVED, S.APPLIED), context) is None


def test_applying_is_a_dedicated_action_with_a_hint() -> None:
    assert (S.SAVED, S.APPLIED) in DEDICATED_ACTIONS
    assert stage_change_hint(S.SAVED) == "Apply in step 3 below"
    for stage in Stage:
        if stage is not S.SAVED:
            assert stage_change_hint(stage) is None


def test_the_options_for_a_user_omit_the_dedicated_transitions() -> None:
    assert allowed_next(S.SAVED) == [S.APPLIED, S.WITHDRAWN]  # the table is unchanged
    assert allowed_next_for_user(S.SAVED) == [S.WITHDRAWN]
    for stage in Stage:
        if stage is not S.SAVED:
            assert allowed_next_for_user(stage) == allowed_next(stage)
