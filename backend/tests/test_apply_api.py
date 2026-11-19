"""POST /applications/{id}/apply, GET /applications/{id}/submittable-resumes and the fields the
application response gains in feature 11: the submitted resume, the applied date, the stage
change hint and the three workflow steps."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.sinks import DatabaseLogSink
from tests.conftest import FakeClock
from tests.fakes import FakeAIClient
from tests.test_resume_review_api import row
from tests.test_tailored_resumes_api import (
    APPLICATION,
    BASE,
    TAILORED,
    count,
    make_analysis,
    save_base,
    tailor,
    use_ai,
)

KEYWORDS = ["ruby on rails", "postgresql"]


def apply(client: TestClient, application_id: int, body: dict | None = None):  # noqa: ANN201
    return client.post(f"/applications/{application_id}/apply", json=body or {})


def application(client: TestClient, application_id: int) -> dict:
    response = client.get(f"/applications/{application_id}")
    assert response.status_code == 200, response.text
    return response.json()


def statuses(body: dict) -> dict[str, str]:
    return {step["key"]: step["status"] for step in body["steps"]}


def new_application(client: TestClient, **overrides: str) -> int:
    response = client.post("/applications", json={**APPLICATION, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def approved_tailored(client: TestClient, sink: DatabaseLogSink, application_id: int) -> int:
    """An approved analysis, then a tailored resume that is approved. Needs a base resume."""
    make_analysis(client, sink, application_id, keywords=KEYWORDS, decision="approve")
    use_ai(FakeAIClient(sink, output=TAILORED))
    resume_id = tailor(client, application_id)["id"]
    assert client.post(f"/resumes/{resume_id}/approve").status_code == 200
    return resume_id


def draft_tailored(client: TestClient, sink: DatabaseLogSink, application_id: int) -> int:
    make_analysis(client, sink, application_id, keywords=KEYWORDS, decision="approve")
    use_ai(FakeAIClient(sink, output=TAILORED))
    return tailor(client, application_id)["id"]


@pytest.fixture
def application_id(client: TestClient) -> int:
    return new_application(client)


@pytest.fixture
def base_saved(client: TestClient) -> None:
    save_base(client)


@pytest.fixture
def approved(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, base_saved: None
) -> int:
    """The id of an approved tailored resume of the application."""
    return approved_tailored(client, db_sink, application_id)


# --- the guard: a choice is required ------------------------------------------------------------


def test_apply_without_a_choice_is_refused_and_changes_nothing(
    client: TestClient, application_id: int, base_saved: None, test_engine: Engine
) -> None:
    response = apply(client, application_id, {})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Choose the resume you sent."
    assert application(client, application_id)["stage"] == "saved"
    assert count(test_engine, "resumes", "application_id IS NOT NULL") == 0
    assert count(test_engine, "timeline_events") == 1


def test_apply_with_an_unknown_choice_is_a_validation_error(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    assert apply(client, application_id, {"choice": "other"}).status_code == 422


def test_apply_refuses_an_extra_field(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    assert apply(client, application_id, {"choice": "base", "extra": 1}).status_code == 422


def test_apply_with_the_base_resume_needs_a_base_resume(
    client: TestClient, application_id: int, test_engine: Engine
) -> None:
    response = apply(client, application_id, {"choice": "base"})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Save a base resume before applying."
    assert application(client, application_id)["stage"] == "saved"


def test_apply_with_a_tailored_choice_needs_a_resume_id(
    client: TestClient, application_id: int, approved: int
) -> None:
    response = apply(client, application_id, {"choice": "tailored"})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Choose which tailored resume you sent."


def test_apply_with_a_draft_resume_is_refused(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, base_saved: None
) -> None:
    resume_id = draft_tailored(client, db_sink, application_id)

    response = apply(client, application_id, {"choice": "tailored", "resume_id": resume_id})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Approve this draft first"
    assert application(client, application_id)["stage"] == "saved"


def test_apply_with_a_rejected_resume_is_refused(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, base_saved: None
) -> None:
    resume_id = draft_tailored(client, db_sink, application_id)
    assert client.post(f"/resumes/{resume_id}/reject").status_code == 200

    response = apply(client, application_id, {"choice": "tailored", "resume_id": resume_id})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "This draft was rejected"


def test_apply_with_another_applications_resume_is_refused(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, approved: int
) -> None:
    other = new_application(client, company="Larkspur Health")
    other_resume = approved_tailored(client, db_sink, other)

    response = apply(client, application_id, {"choice": "tailored", "resume_id": other_resume})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "That resume belongs to another application"
    assert application(client, application_id)["stage"] == "saved"


def test_apply_with_a_resume_that_does_not_exist_is_refused(
    client: TestClient, application_id: int, approved: int
) -> None:
    response = apply(client, application_id, {"choice": "tailored", "resume_id": 9999})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "That tailored resume was not found."


def test_apply_with_the_base_row_as_a_tailored_resume_is_refused(
    client: TestClient, application_id: int, approved: int, test_engine: Engine
) -> None:
    with test_engine.connect() as conn:
        base_id = conn.execute(
            text("SELECT id FROM resumes WHERE application_id IS NULL")
        ).scalar_one()

    response = apply(client, application_id, {"choice": "tailored", "resume_id": base_id})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "That is not a tailored resume"


def test_apply_to_an_unknown_application_is_404(client: TestClient, base_saved: None) -> None:
    assert apply(client, 999, {"choice": "base"}).status_code == 404


def test_apply_to_an_application_that_left_saved_is_409(
    client: TestClient, application_id: int, base_saved: None, test_engine: Engine
) -> None:
    assert apply(client, application_id, {"choice": "base"}).status_code == 200
    snapshots = count(test_engine, "resumes", "application_id IS NOT NULL")

    response = apply(client, application_id, {"choice": "base"})

    assert response.status_code == 409
    assert count(test_engine, "resumes", "application_id IS NOT NULL") == snapshots


# --- applying with a tailored resume ------------------------------------------------------------


def test_apply_with_a_tailored_resume_points_at_it_and_makes_no_new_resume(
    client: TestClient, application_id: int, approved: int, test_engine: Engine, clock: FakeClock
) -> None:
    resumes_before = count(test_engine, "resumes")
    clock.advance(days=2)

    response = apply(client, application_id, {"choice": "tailored", "resume_id": approved})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stage"] == "applied"
    assert body["submitted_resume"]["id"] == approved
    assert body["submitted_resume"]["kind"] == "tailored"
    assert datetime.fromisoformat(body["applied_at"]) == clock.now
    assert count(test_engine, "resumes") == resumes_before


def test_apply_writes_the_stage_change_event(
    client: TestClient, application_id: int, approved: int, test_engine: Engine
) -> None:
    apply(client, application_id, {"choice": "tailored", "resume_id": approved})

    events = client.get(f"/applications/{application_id}/timeline").json()
    assert (events[0]["from_stage"], events[0]["to_stage"]) == ("saved", "applied")


def test_an_older_approved_tailored_resume_may_still_be_sent(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, approved: int
) -> None:
    use_ai(FakeAIClient(db_sink, output=TAILORED))
    tailor(client, application_id)  # a newer draft supersedes the approved one

    response = apply(client, application_id, {"choice": "tailored", "resume_id": approved})

    assert response.status_code == 200


# --- applying with the base resume: the snapshot ------------------------------------------------


def test_apply_with_the_base_resume_saves_a_snapshot_of_it(
    client: TestClient, application_id: int, base_saved: None, test_engine: Engine, clock: FakeClock
) -> None:
    response = apply(client, application_id, {"choice": "base"})

    assert response.status_code == 200, response.text
    body = response.json()
    snapshot = row(test_engine, body["submitted_resume"]["id"])
    assert snapshot["application_id"] == application_id
    assert snapshot["ai_call_id"] is None
    assert snapshot["status"] == "approved"
    assert snapshot["content_markdown"] == BASE
    assert snapshot["draft_markdown"] is None
    assert snapshot["content_json"] is None
    assert snapshot["guardrail_flags"] == []
    assert snapshot["created_at"] == clock.now
    assert body["submitted_resume"]["kind"] == "base"
    assert body["stage"] == "applied"


def test_the_snapshot_is_a_new_row_and_the_base_resume_is_untouched(
    client: TestClient, application_id: int, base_saved: None, test_engine: Engine
) -> None:
    with test_engine.connect() as conn:
        before = conn.execute(text("SELECT * FROM resumes")).mappings().one()
    before = dict(before)

    body = apply(client, application_id, {"choice": "base"}).json()

    assert body["submitted_resume"]["id"] != before["id"]
    assert count(test_engine, "resumes") == 2
    assert row(test_engine, before["id"]) == before
    assert client.get("/resume").json()["content_markdown"] == BASE


def test_the_tailored_resume_stays_with_the_application_when_the_base_is_sent(
    client: TestClient, application_id: int, approved: int
) -> None:
    body = apply(client, application_id, {"choice": "base"}).json()

    listed = client.get(f"/applications/{application_id}/tailored-resumes").json()
    assert [resume["id"] for resume in listed] == [approved]
    assert body["submitted_resume"]["id"] != approved


def test_a_later_edit_of_the_base_resume_does_not_change_the_snapshot(
    client: TestClient, application_id: int, base_saved: None, test_engine: Engine
) -> None:
    snapshot_id = apply(client, application_id, {"choice": "base"}).json()["submitted_resume"]["id"]

    assert client.put("/resume", json={"content_markdown": "# Someone else"}).status_code == 200

    assert row(test_engine, snapshot_id)["content_markdown"] == BASE
    assert client.get("/resume").json()["content_markdown"] == "# Someone else"
    assert application(client, application_id)["submitted_resume"]["id"] == snapshot_id


def test_a_snapshot_is_not_a_tailored_resume(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    apply(client, application_id, {"choice": "base"})

    assert client.get(f"/applications/{application_id}/tailored-resumes").json() == []
    body = application(client, application_id)
    assert statuses(body)["tailored"] == "skipped"


def test_a_snapshot_cannot_be_reviewed_like_a_tailored_resume(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    snapshot_id = apply(client, application_id, {"choice": "base"}).json()["submitted_resume"]["id"]

    assert client.post(f"/resumes/{snapshot_id}/reject").status_code == 404
    assert (
        client.patch(f"/resumes/{snapshot_id}", json={"content_markdown": "x"}).status_code == 404
    )


# --- the generic stage endpoint -----------------------------------------------------------------


def test_the_generic_stage_endpoint_rejects_saved_to_applied(
    client: TestClient, application_id: int, base_saved: None, test_engine: Engine
) -> None:
    response = client.post(f"/applications/{application_id}/stage", json={"to_stage": "applied"})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Choose the resume you sent."
    assert application(client, application_id)["stage"] == "saved"
    assert count(test_engine, "resumes", "application_id IS NOT NULL") == 0


def test_the_generic_stage_endpoint_still_withdraws_a_saved_application(
    client: TestClient, application_id: int
) -> None:
    response = client.post(f"/applications/{application_id}/stage", json={"to_stage": "withdrawn"})

    assert response.status_code == 200
    assert response.json()["stage"] == "withdrawn"
    assert response.json()["submitted_resume"] is None


def test_the_generic_endpoint_does_not_list_applied_as_an_option(
    client: TestClient, application_id: int
) -> None:
    response = client.post(f"/applications/{application_id}/stage", json={"to_stage": "offer"})

    assert response.status_code == 409
    assert response.json()["detail"]["allowed_next_stages"] == ["withdrawn"]


def test_other_transitions_are_unchanged(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    apply(client, application_id, {"choice": "base"})

    moved = client.post(f"/applications/{application_id}/stage", json={"to_stage": "screening"})

    assert moved.status_code == 200
    assert moved.json()["stage"] == "screening"
    assert moved.json()["submitted_resume"]["kind"] == "base"  # it stays with the application


# --- the application response -------------------------------------------------------------------


def test_a_saved_application_omits_applied_and_carries_the_hint(
    client: TestClient, application_id: int
) -> None:
    body = application(client, application_id)

    assert body["allowed_next_stages"] == ["withdrawn"]
    assert body["stage_change_hint"] == "Apply in step 3 below"
    assert body["submitted_resume"] is None
    assert body["applied_at"] is None


def test_an_applied_application_has_no_hint_and_its_usual_options(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    body = apply(client, application_id, {"choice": "base"}).json()

    assert body["allowed_next_stages"] == ["screening", "interviewing", "rejected", "withdrawn"]
    assert body["stage_change_hint"] is None


def test_the_applied_date_is_when_the_application_moved_to_applied(
    client: TestClient, application_id: int, base_saved: None, clock: FakeClock
) -> None:
    clock.advance(days=3)
    applied_on = clock.now
    apply(client, application_id, {"choice": "base"})
    clock.advance(days=5)
    client.post(f"/applications/{application_id}/stage", json={"to_stage": "screening"})

    body = application(client, application_id)

    assert datetime.fromisoformat(body["applied_at"]) == applied_on


def test_a_withdrawn_application_has_no_applied_date_and_no_submitted_resume(
    client: TestClient, application_id: int
) -> None:
    client.post(f"/applications/{application_id}/stage", json={"to_stage": "withdrawn"})

    body = application(client, application_id)

    assert body["applied_at"] is None
    assert body["submitted_resume"] is None


def test_the_response_carries_the_three_steps_in_order(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    body = application(client, application_id)

    assert [step["key"] for step in body["steps"]] == ["analysis", "tailored", "apply"]
    assert statuses(body) == {"analysis": "current", "tailored": "locked", "apply": "available"}
    assert all(step["text"] for step in body["steps"])


def test_step_3_is_locked_without_a_base_resume(client: TestClient, application_id: int) -> None:
    assert statuses(application(client, application_id))["apply"] == "locked"


def test_the_steps_follow_the_work_done(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, base_saved: None
) -> None:
    make_analysis(client, db_sink, application_id, keywords=KEYWORDS, decision="approve")
    assert statuses(application(client, application_id)) == {
        "analysis": "done",
        "tailored": "current",
        "apply": "available",
    }

    use_ai(FakeAIClient(db_sink, output=TAILORED))
    resume_id = tailor(client, application_id)["id"]
    client.post(f"/resumes/{resume_id}/approve")

    assert statuses(application(client, application_id)) == {
        "analysis": "done",
        "tailored": "done",
        "apply": "current",
    }

    apply(client, application_id, {"choice": "tailored", "resume_id": resume_id})

    assert statuses(application(client, application_id)) == {
        "analysis": "done",
        "tailored": "done",
        "apply": "done",
    }


def test_an_application_withdrawn_from_saved_is_skipped_never_done(
    client: TestClient, application_id: int, base_saved: None
) -> None:
    client.post(f"/applications/{application_id}/stage", json={"to_stage": "withdrawn"})

    assert statuses(application(client, application_id)) == {
        "analysis": "skipped",
        "tailored": "skipped",
        "apply": "skipped",
    }


def test_the_list_carries_the_submitted_resume_and_the_steps(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, approved: int
) -> None:
    sent = new_application(client, company="Larkspur Health")
    untouched = new_application(client, company="Tallgrass Payments")
    apply(client, application_id, {"choice": "tailored", "resume_id": approved})
    apply(client, sent, {"choice": "base"})

    items = {item["id"]: item for item in client.get("/applications").json()["items"]}

    assert items[application_id]["submitted_resume"]["kind"] == "tailored"
    assert items[sent]["submitted_resume"]["kind"] == "base"
    assert items[untouched]["submitted_resume"] is None
    assert statuses(items[application_id]) == statuses(application(client, application_id))
    assert statuses(items[sent]) == statuses(application(client, sent))
    assert statuses(items[untouched]) == statuses(application(client, untouched))
    assert items[sent]["applied_at"] == application(client, sent)["applied_at"]


# --- GET /applications/{id}/submittable-resumes -------------------------------------------------


def submittable(client: TestClient, application_id: int) -> list[dict]:
    response = client.get(f"/applications/{application_id}/submittable-resumes")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_submittable_list_has_the_tailored_resumes_then_the_base_resume(
    client: TestClient, application_id: int, approved: int
) -> None:
    options = submittable(client, application_id)

    assert [(o["kind"], o["submittable"]) for o in options] == [("tailored", True), ("base", True)]
    assert options[0]["id"] == approved
    assert options[0]["status"] == "approved"
    assert options[1]["status"] == "approved"
    assert all(option["date"] for option in options)
    assert all(option["reason"] is None for option in options)


def test_a_draft_is_listed_but_not_submittable_and_says_why(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, base_saved: None
) -> None:
    resume_id = draft_tailored(client, db_sink, application_id)

    options = submittable(client, application_id)

    draft = next(option for option in options if option["id"] == resume_id)
    assert draft["submittable"] is False
    assert draft["reason"] == "Approve this draft first"
    assert draft["status"] == "draft"


def test_a_rejected_resume_is_listed_but_not_submittable(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, base_saved: None
) -> None:
    resume_id = draft_tailored(client, db_sink, application_id)
    client.post(f"/resumes/{resume_id}/reject")

    option = submittable(client, application_id)[0]

    assert (option["submittable"], option["reason"]) == (False, "This draft was rejected")


def test_tailored_resumes_are_listed_newest_first(
    client: TestClient,
    db_sink: DatabaseLogSink,
    application_id: int,
    approved: int,
    clock: FakeClock,
) -> None:
    clock.advance(hours=1)
    use_ai(FakeAIClient(db_sink, output=TAILORED))
    newer = tailor(client, application_id)["id"]

    options = submittable(client, application_id)

    assert [o["id"] for o in options[:2]] == [newer, approved]
    assert options[2]["kind"] == "base"


def test_the_list_has_no_base_option_before_a_base_resume_is_saved(
    client: TestClient, application_id: int
) -> None:
    assert submittable(client, application_id) == []


def test_the_list_holds_only_this_applications_resumes(
    client: TestClient, db_sink: DatabaseLogSink, application_id: int, approved: int
) -> None:
    other = new_application(client, company="Larkspur Health")
    approved_tailored(client, db_sink, other)

    options = submittable(client, application_id)

    assert [o["kind"] for o in options] == ["tailored", "base"]


def test_a_snapshot_is_not_listed_as_an_option(
    client: TestClient, db_sink: DatabaseLogSink, base_saved: None
) -> None:
    sent = new_application(client, company="Larkspur Health")
    apply(client, sent, {"choice": "base"})
    other = new_application(client, company="Tallgrass Payments")

    assert [o["kind"] for o in submittable(client, other)] == ["base"]


def test_the_submittable_list_for_an_unknown_application_is_404(client: TestClient) -> None:
    assert client.get("/applications/999/submittable-resumes").status_code == 404


def test_the_new_endpoints_are_in_the_api_docs(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "post" in paths["/applications/{application_id}/apply"]
    assert "get" in paths["/applications/{application_id}/submittable-resumes"]
