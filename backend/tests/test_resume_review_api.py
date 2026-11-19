"""The review endpoints for a tailored resume: edit, approve and reject, and which resume the
list marks as displayed. Nothing here makes a new resume row or calls the AI."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.sinks import DatabaseLogSink
from app.services.rendering import render_tailored_markdown
from tests.conftest import FakeClock
from tests.fakes import FakeAIClient
from tests.test_tailored_resumes_api import (
    APPLICATION,
    BASE,
    DIRTY_FIELDS,
    TAILORED,
    count,
    make_analysis,
    save_base,
    tailor,
    use_ai,
)

# The base resume has the first two keywords. The other two are not in it.
KEYWORDS = ["ruby on rails", "postgresql", "kubernetes", "aws"]
GENERATED = render_tailored_markdown(BASE, TAILORED)
SKILLS = "Ruby on Rails, PostgreSQL"


@pytest.fixture
def application_id(client: TestClient) -> int:
    response = client.post("/applications", json=APPLICATION)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
def ready(client: TestClient, db_sink: DatabaseLogSink, application_id: int) -> FakeAIClient:
    make_analysis(client, db_sink, application_id, keywords=KEYWORDS, decision="approve")
    save_base(client)
    fake = FakeAIClient(db_sink, output=TAILORED)
    use_ai(fake)
    return fake


@pytest.fixture
def draft(client: TestClient, ready: FakeAIClient, application_id: int) -> dict:
    """One tailored resume, still a draft."""
    return tailor(client, application_id)


def listing(client: TestClient, application_id: int) -> list[dict]:
    response = client.get(f"/applications/{application_id}/tailored-resumes")
    assert response.status_code == 200, response.text
    return response.json()


def row(engine: Engine, resume_id: int) -> dict:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM resumes WHERE id = :id"), {"id": resume_id})
        return dict(result.mappings().one())


def edit(client: TestClient, resume_id: int, markdown: str):  # noqa: ANN201
    return client.patch(f"/resumes/{resume_id}", json={"content_markdown": markdown})


# --- PATCH: what an edit changes ----------------------------------------------------------------


def test_patch_saves_the_text_and_leaves_the_status_draft(client: TestClient, draft: dict) -> None:
    text_ = GENERATED.replace("Backend lead on Ruby on Rails.", "Backend lead.")

    response = edit(client, draft["id"], text_)

    assert response.status_code == 200
    body = response.json()
    assert body["content_markdown"] == text_
    assert body["status"] == "draft"
    assert body["reviewed_at"] is None
    assert body["outcome"] == "pending"
    assert listing(client, draft["application_id"])[0]["content_markdown"] == text_


def test_patch_changes_only_the_text_and_the_update_time(
    client: TestClient, draft: dict, test_engine: Engine, clock: FakeClock
) -> None:
    before = row(test_engine, draft["id"])
    clock.advance(hours=2)

    edit(client, draft["id"], GENERATED + "\nExtra line.\n")

    after = row(test_engine, draft["id"])
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"content_markdown", "updated_at"}
    assert after["updated_at"] == clock.now


def test_patch_never_changes_the_generated_text(
    client: TestClient, draft: dict, test_engine: Engine
) -> None:
    edit(client, draft["id"], "Something completely different.")
    edit(client, draft["id"], "And again.")

    assert row(test_engine, draft["id"])["draft_markdown"] == GENERATED


def test_the_database_still_refuses_a_direct_change_to_the_generated_text(
    client: TestClient, draft: dict, test_engine: Engine
) -> None:
    with pytest.raises(Exception, match="draft_markdown cannot change"):
        with test_engine.begin() as conn:
            conn.execute(
                text("UPDATE resumes SET draft_markdown = 'x' WHERE id = :id"), {"id": draft["id"]}
            )


def test_patch_stores_the_text_exactly_as_given(client: TestClient, draft: dict) -> None:
    exact = "  # Jordan\n\n\ttabbed   line  \n\n"

    edit(client, draft["id"], exact)

    assert listing(client, draft["application_id"])[0]["content_markdown"] == exact


def test_patch_cannot_set_a_status_or_any_other_field(
    client: TestClient, draft: dict, test_engine: Engine
) -> None:
    for extra in ({"status": "approved"}, {"draft_markdown": "x"}, {"reviewed_at": "2026-01-01"}):
        response = client.patch(
            f"/resumes/{draft['id']}", json={"content_markdown": "New", **extra}
        )

        assert response.status_code == 422

    after = row(test_engine, draft["id"])
    assert after["status"] == "draft"
    assert after["content_markdown"] == GENERATED


@pytest.mark.parametrize("body", [{"content_markdown": ""}, {"content_markdown": "  \n\t "}, {}])
def test_patch_with_blank_or_missing_text_is_422_and_changes_nothing(
    client: TestClient, draft: dict, body: dict
) -> None:
    response = client.patch(f"/resumes/{draft['id']}", json=body)

    assert response.status_code == 422
    assert listing(client, draft["application_id"])[0]["content_markdown"] == GENERATED


def test_patch_makes_no_new_row_no_ai_call_and_no_timeline_event(
    client: TestClient, ready: FakeAIClient, draft: dict, test_engine: Engine
) -> None:
    resumes = count(test_engine, "resumes")
    events = count(test_engine, "timeline_events")
    ai_calls = count(test_engine, "ai_calls")
    calls = len(ready.calls)

    edit(client, draft["id"], "Edited.")

    assert count(test_engine, "resumes") == resumes
    assert count(test_engine, "timeline_events") == events
    assert count(test_engine, "ai_calls") == ai_calls
    assert len(ready.calls) == calls


# --- PATCH: coverage and flags come back with the save -----------------------------------------


def test_patch_returns_the_coverage_of_the_saved_text_against_the_base_resume(
    client: TestClient, draft: dict
) -> None:
    edited = GENERATED.replace(SKILLS, f"{SKILLS}, Kubernetes")

    coverage = edit(client, draft["id"], edited).json()["coverage"]

    assert coverage["ratio"] == 0.75
    assert coverage["covered"] == ["ruby on rails", "postgresql", "kubernetes"]
    assert coverage["missing"] == ["aws"]
    assert coverage["base"]["ratio"] == 0.5
    assert coverage["newly_covered"] == ["kubernetes"]
    assert coverage["still_missing"] == ["aws"]


def test_patch_coverage_drops_a_keyword_the_edit_removed(client: TestClient, draft: dict) -> None:
    coverage = edit(client, draft["id"], "# Jordan Avery\n\nNothing relevant.\n").json()["coverage"]

    assert coverage["covered"] == []
    assert coverage["ratio"] == 0.0
    assert coverage["newly_covered"] == []
    assert coverage["base"]["covered"] == ["ruby on rails", "postgresql"]


def test_patch_returns_the_flags_for_the_text_as_saved(client: TestClient, draft: dict) -> None:
    assert [f["field"] for f in draft["guardrail_flags"]] == DIRTY_FIELDS

    without_number = edit(client, draft["id"], GENERATED.replace("Led a team of 5", "Led a team"))
    with_keyword = edit(client, draft["id"], GENERATED.replace(SKILLS, f"{SKILLS}, Kubernetes"))

    assert [f["field"] for f in without_number.json()["guardrail_flags"]] == [
        "employer",
        "title",
        "dates",
    ]
    assert [f["field"] for f in with_keyword.json()["guardrail_flags"]] == [
        *DIRTY_FIELDS,
        "keyword",
    ]


def test_patch_leaves_the_stored_flags_as_generated(
    client: TestClient, draft: dict, test_engine: Engine
) -> None:
    before = row(test_engine, draft["id"])["guardrail_flags"]

    edit(client, draft["id"], GENERATED.replace("Led a team of 5", "Led a team"))

    assert row(test_engine, draft["id"])["guardrail_flags"] == before


def test_get_shows_the_same_flags_as_the_patch_response(client: TestClient, draft: dict) -> None:
    saved = edit(client, draft["id"], GENERATED.replace("Led a team of 5", "Led a team")).json()

    [listed] = listing(client, draft["application_id"])

    assert listed["guardrail_flags"] == saved["guardrail_flags"]


# --- PATCH: refusals ----------------------------------------------------------------------------


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_patch_after_a_decision_is_409_and_changes_nothing(
    client: TestClient, draft: dict, test_engine: Engine, decision: str
) -> None:
    assert client.post(f"/resumes/{draft['id']}/{decision}").status_code == 200
    before = row(test_engine, draft["id"])

    response = edit(client, draft["id"], "Too late.")

    assert response.status_code == 409
    assert response.json()["detail"] == "only a draft can be edited"
    assert row(test_engine, draft["id"]) == before


def test_every_review_endpoint_has_a_description_in_the_docs() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    for path, method in [
        ("/resumes/{resume_id}", "patch"),
        ("/resumes/{resume_id}/approve", "post"),
        ("/resumes/{resume_id}/reject", "post"),
    ]:
        assert paths[path][method].get("description"), f"{method.upper()} {path} has none"


def test_patch_for_an_unknown_resume_is_404(client: TestClient) -> None:
    assert edit(client, 999, "Text").status_code == 404


def test_patch_cannot_reach_the_base_resume(client: TestClient, draft: dict) -> None:
    base_id = client.get("/resume").json()["id"]

    response = edit(client, base_id, "Overwritten through the wrong endpoint.")

    assert response.status_code == 404
    assert client.get("/resume").json()["content_markdown"] == BASE


def test_patch_cannot_reach_a_base_resume_snapshot(
    client: TestClient, application_id: int, test_engine: Engine
) -> None:
    # A snapshot is a resume of this application that no AI call made (feature 11).
    with test_engine.begin() as conn:
        snapshot_id = conn.execute(
            text(
                "INSERT INTO resumes (application_id, content_markdown, status) "
                "VALUES (:application_id, 'snapshot of the base', 'approved') RETURNING id"
            ),
            {"application_id": application_id},
        ).scalar_one()

    assert edit(client, snapshot_id, "Changed").status_code == 404
    assert client.post(f"/resumes/{snapshot_id}/reject").status_code == 404
    assert row(test_engine, snapshot_id)["content_markdown"] == "snapshot of the base"


# --- approve and reject -------------------------------------------------------------------------


def test_approve_sets_the_status_and_the_review_time(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    clock.advance(days=1)

    response = client.post(f"/resumes/{draft['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert datetime.fromisoformat(body["reviewed_at"]) == clock.now
    assert body["outcome"] == "approved"
    assert body["content_markdown"] == GENERATED


def test_approve_after_an_edit_keeps_the_edit_and_is_edited_then_approved(
    client: TestClient, draft: dict, test_engine: Engine
) -> None:
    edit(client, draft["id"], GENERATED + "\nAn extra line.\n")

    response = client.post(f"/resumes/{draft['id']}/approve")

    body = response.json()
    assert body["outcome"] == "edited_then_approved"
    assert body["content_markdown"] == GENERATED + "\nAn extra line.\n"
    assert row(test_engine, draft["id"])["draft_markdown"] == GENERATED


def test_reject_sets_the_status_and_the_review_time(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    clock.advance(days=1)

    response = client.post(f"/resumes/{draft['id']}/reject")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert datetime.fromisoformat(body["reviewed_at"]) == clock.now
    assert body["outcome"] == "rejected"


@pytest.mark.parametrize("first", ["approve", "reject"])
@pytest.mark.parametrize("second", ["approve", "reject"])
def test_a_decided_resume_cannot_be_decided_again(
    client: TestClient, draft: dict, test_engine: Engine, clock: FakeClock, first: str, second: str
) -> None:
    client.post(f"/resumes/{draft['id']}/{first}")
    before = row(test_engine, draft["id"])
    clock.advance(days=1)

    response = client.post(f"/resumes/{draft['id']}/{second}")

    assert response.status_code == 409
    assert row(test_engine, draft["id"]) == before


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_a_decision_on_an_unknown_resume_is_404(client: TestClient, decision: str) -> None:
    assert client.post(f"/resumes/999/{decision}").status_code == 404


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_a_decision_cannot_reach_the_base_resume(
    client: TestClient, draft: dict, test_engine: Engine, decision: str
) -> None:
    base_id = client.get("/resume").json()["id"]

    assert client.post(f"/resumes/{base_id}/{decision}").status_code == 404
    assert row(test_engine, base_id)["status"] == "approved"
    assert row(test_engine, base_id)["reviewed_at"] is None


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_a_decision_makes_no_row_no_ai_call_no_timeline_event_and_no_stage_change(
    client: TestClient, draft: dict, test_engine: Engine, decision: str
) -> None:
    resumes = count(test_engine, "resumes")
    events = count(test_engine, "timeline_events")
    ai_calls = count(test_engine, "ai_calls")

    client.post(f"/resumes/{draft['id']}/{decision}")

    assert count(test_engine, "resumes") == resumes
    assert count(test_engine, "timeline_events") == events
    assert count(test_engine, "ai_calls") == ai_calls
    assert count(test_engine, "applications", "stage = 'saved'") == 1


def test_a_decision_is_not_blocked_by_guardrail_flags(client: TestClient, draft: dict) -> None:
    assert draft["guardrail_flags"]

    assert client.post(f"/resumes/{draft['id']}/approve").status_code == 200


# --- which resume is displayed, and each one's outcome ------------------------------------------


def tailor_later(client: TestClient, application_id: int, clock: FakeClock) -> dict:
    clock.advance(hours=1)
    return tailor(client, application_id)


def displayed(resumes: list[dict]) -> list[int]:
    return [r["id"] for r in resumes if r["displayed"]]


def test_a_new_draft_is_displayed_and_pending_with_no_review_time(draft: dict) -> None:
    assert draft["displayed"] is True
    assert draft["outcome"] == "pending"
    assert draft["reviewed_at"] is None


def test_the_newest_draft_is_displayed_and_an_older_one_is_superseded(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    newer = tailor_later(client, draft["application_id"], clock)

    older_row, newer_row = reversed(listing(client, draft["application_id"]))

    assert (older_row["id"], newer_row["id"]) == (draft["id"], newer["id"])
    assert displayed([older_row, newer_row]) == [newer["id"]]
    assert older_row["outcome"] == "superseded"
    assert newer_row["outcome"] == "pending"


def test_a_pending_draft_is_displayed_ahead_of_an_older_approved_resume(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    client.post(f"/resumes/{draft['id']}/approve")
    newer = tailor_later(client, draft["application_id"], clock)

    resumes = listing(client, draft["application_id"])

    assert displayed(resumes) == [newer["id"]]
    assert {r["id"]: r["outcome"] for r in resumes} == {
        draft["id"]: "approved",
        newer["id"]: "pending",
    }


def test_the_approved_resume_is_displayed_when_no_draft_is_waiting(
    client: TestClient, draft: dict
) -> None:
    client.post(f"/resumes/{draft['id']}/approve")

    assert displayed(listing(client, draft["application_id"])) == [draft["id"]]


def test_the_latest_approved_resume_is_displayed_over_a_newer_rejected_one(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    client.post(f"/resumes/{draft['id']}/approve")
    newer = tailor_later(client, draft["application_id"], clock)

    client.post(f"/resumes/{newer['id']}/reject")

    assert displayed(listing(client, draft["application_id"])) == [draft["id"]]


def test_the_newer_of_two_approved_resumes_is_displayed(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    client.post(f"/resumes/{draft['id']}/approve")
    newer = tailor_later(client, draft["application_id"], clock)
    client.post(f"/resumes/{newer['id']}/approve")

    assert displayed(listing(client, draft["application_id"])) == [newer["id"]]


def test_the_latest_rejected_resume_is_displayed_when_none_is_approved_or_waiting(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    client.post(f"/resumes/{draft['id']}/reject")
    newer = tailor_later(client, draft["application_id"], clock)
    client.post(f"/resumes/{newer['id']}/reject")

    assert displayed(listing(client, draft["application_id"])) == [newer["id"]]


def test_a_rejected_newest_resume_hides_an_older_draft_that_was_superseded(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    # The older draft has a newer draft (now rejected), so it is superseded, not awaiting review.
    newer = tailor_later(client, draft["application_id"], clock)
    client.post(f"/resumes/{newer['id']}/reject")

    resumes = listing(client, draft["application_id"])

    assert displayed(resumes) == [newer["id"]]
    assert {r["id"]: r["outcome"] for r in resumes} == {
        draft["id"]: "superseded",
        newer["id"]: "rejected",
    }


def test_a_draft_becomes_superseded_when_a_newer_resume_is_approved(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    newer = tailor_later(client, draft["application_id"], clock)
    client.post(f"/resumes/{newer['id']}/approve")

    outcomes = {r["id"]: r["outcome"] for r in listing(client, draft["application_id"])}

    assert outcomes == {draft["id"]: "superseded", newer["id"]: "approved"}


def test_superseding_never_changes_the_older_draft_or_rejects_it(
    client: TestClient, draft: dict, clock: FakeClock, test_engine: Engine
) -> None:
    before = row(test_engine, draft["id"])

    newer = tailor_later(client, draft["application_id"], clock)
    client.post(f"/resumes/{newer['id']}/approve")

    assert row(test_engine, draft["id"]) == before
    assert row(test_engine, draft["id"])["status"] == "draft"


def test_a_superseded_draft_can_still_be_decided_by_the_user(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    tailor_later(client, draft["application_id"], clock)

    assert client.post(f"/resumes/{draft['id']}/reject").status_code == 200


def test_a_decision_response_says_which_resume_is_displayed_afterwards(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    client.post(f"/resumes/{draft['id']}/approve")
    newer = tailor_later(client, draft["application_id"], clock)

    rejected = client.post(f"/resumes/{newer['id']}/reject").json()

    assert rejected["displayed"] is False  # the older approved resume is displayed again


def test_exactly_one_resume_is_displayed_per_application(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    second = tailor_later(client, draft["application_id"], clock)
    tailor_later(client, draft["application_id"], clock)
    client.post(f"/resumes/{second['id']}/approve")

    assert len(displayed(listing(client, draft["application_id"]))) == 1


def test_another_applications_resumes_do_not_supersede_or_get_displayed_here(
    client: TestClient, draft: dict
) -> None:
    other = client.post("/applications", json=APPLICATION).json()["id"]

    assert listing(client, other) == []
    assert listing(client, draft["application_id"])[0]["outcome"] == "pending"


def test_the_list_with_no_resumes_displays_nothing(client: TestClient, application_id: int) -> None:
    assert listing(client, application_id) == []


def test_the_approval_date_is_returned_with_the_list(
    client: TestClient, draft: dict, clock: FakeClock
) -> None:
    clock.advance(days=2)
    client.post(f"/resumes/{draft['id']}/approve")

    [resume] = listing(client, draft["application_id"])

    assert datetime.fromisoformat(resume["reviewed_at"]) == clock.now
