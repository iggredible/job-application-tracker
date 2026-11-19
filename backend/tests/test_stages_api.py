"""POST /stage, POST /notes, GET /timeline, the stage filter and the derived response fields."""

from datetime import datetime

from fastapi.testclient import TestClient

from tests.conftest import FakeClock

VALID = {
    "company": "Northwind Freight",
    "role": "Senior Backend Engineer",
    "source": "linkedin",
    "posting_url": "https://northwind.example/careers/1",
    "posting_text": "Build services.",
}
STAGES = [
    "saved", "applied", "screening", "interviewing",
    "offer", "accepted", "rejected", "withdrawn",
]  # fmt: skip


def create(client: TestClient, **overrides) -> dict:
    response = client.post("/applications", json={**VALID, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def move(client: TestClient, application_id: int, to_stage: str):
    return client.post(f"/applications/{application_id}/stage", json={"to_stage": to_stage})


def apply_with_base(client: TestClient, application_id: int):
    """Saved -> Applied goes through the apply action (feature 11), with the base resume."""
    assert client.put("/resume", json={"content_markdown": "# Jordan Avery\n"}).status_code == 200
    response = client.post(f"/applications/{application_id}/apply", json={"choice": "base"})
    assert response.status_code == 200, response.text
    return response


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --- the application response -------------------------------------------------------------


def test_application_response_has_the_derived_fields(client: TestClient, clock: FakeClock) -> None:
    created = create(client)

    assert created["allowed_next_stages"] == ["withdrawn"]
    assert parse(created["last_activity_at"]) == clock.now
    assert created["is_stale"] is False
    assert created["idle_days"] == 0
    assert client.get(f"/applications/{created['id']}").json() == created


def test_patch_response_has_the_derived_fields(client: TestClient) -> None:
    created = create(client)

    body = client.patch(f"/applications/{created['id']}", json={"role": "Lead"}).json()

    assert body["allowed_next_stages"] == ["withdrawn"]
    assert "last_activity_at" in body and "is_stale" in body and "idle_days" in body


def test_application_becomes_stale_after_14_days(client: TestClient, clock: FakeClock) -> None:
    created = create(client)
    url = f"/applications/{created['id']}"

    clock.advance(days=13)
    assert (client.get(url).json()["is_stale"], client.get(url).json()["idle_days"]) == (False, 13)

    clock.advance(days=1)
    body = client.get(url).json()
    assert (body["is_stale"], body["idle_days"]) == (True, 14)


def test_terminal_application_is_not_stale_and_has_no_next_stages(
    client: TestClient, clock: FakeClock
) -> None:
    created = create(client)
    move(client, created["id"], "withdrawn")

    clock.advance(days=30)
    body = client.get(f"/applications/{created['id']}").json()

    assert body["is_stale"] is False
    assert body["allowed_next_stages"] == []


# --- POST /applications/{id}/stage ----------------------------------------------------------


def test_stage_endpoint_moves_the_application(client: TestClient, clock: FakeClock) -> None:
    created = create(client)
    apply_with_base(client, created["id"])
    clock.advance(days=2)

    response = move(client, created["id"], "screening")

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "screening"
    assert body["allowed_next_stages"] == ["interviewing", "rejected", "withdrawn"]
    assert parse(body["last_activity_at"]) == clock.now
    assert client.get(f"/applications/{created['id']}").json()["stage"] == "screening"


def test_invalid_transition_returns_409_with_the_allowed_next_stages(client: TestClient) -> None:
    created = create(client)

    response = move(client, created["id"], "offer")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["allowed_next_stages"] == ["withdrawn"]
    assert "saved" in detail["message"] and "offer" in detail["message"]


def test_invalid_transition_changes_nothing(client: TestClient) -> None:
    created = create(client)

    move(client, created["id"], "offer")

    assert client.get(f"/applications/{created['id']}").json() == created
    assert len(client.get(f"/applications/{created['id']}/timeline").json()) == 1


def test_terminal_stage_returns_409_with_an_empty_allowed_list(client: TestClient) -> None:
    created = create(client)
    move(client, created["id"], "withdrawn")

    for target in STAGES:
        response = move(client, created["id"], target)
        assert response.status_code == 409, target
        assert response.json()["detail"]["allowed_next_stages"] == []


def test_stage_endpoint_rejects_an_unknown_stage_or_bad_body(client: TestClient) -> None:
    created = create(client)
    url = f"/applications/{created['id']}/stage"

    assert client.post(url, json={"to_stage": "promoted"}).status_code == 422
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={"to_stage": "applied", "extra": 1}).status_code == 422
    assert client.post(url, json={"to_stage": None}).status_code == 422


def test_stage_endpoint_unknown_application_returns_404(client: TestClient) -> None:
    assert move(client, 999, "applied").status_code == 404


# --- POST /applications/{id}/notes ----------------------------------------------------------


def test_notes_endpoint_adds_a_note_event(client: TestClient, clock: FakeClock) -> None:
    created = create(client)
    clock.advance(hours=5)

    response = client.post(
        f"/applications/{created['id']}/notes", json={"note": "  Phone screen booked  "}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["application_id"] == created["id"]
    assert body["type"] == "note"
    assert body["note"] == "Phone screen booked"
    assert body["from_stage"] is None and body["to_stage"] is None
    assert parse(body["created_at"]) == clock.now
    assert client.get(f"/applications/{created['id']}").json()["stage"] == "saved"


def test_notes_endpoint_rejects_blank_or_missing_notes(client: TestClient) -> None:
    created = create(client)
    url = f"/applications/{created['id']}/notes"

    assert client.post(url, json={"note": "   "}).status_code == 422
    assert client.post(url, json={"note": ""}).status_code == 422
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={"note": None}).status_code == 422
    assert len(client.get(f"/applications/{created['id']}/timeline").json()) == 1


def test_notes_endpoint_unknown_application_returns_404(client: TestClient) -> None:
    assert client.post("/applications/999/notes", json={"note": "hi"}).status_code == 404


def test_a_note_resets_the_stale_clock_through_the_api(
    client: TestClient, clock: FakeClock
) -> None:
    created = create(client)
    clock.advance(days=20)
    assert client.get(f"/applications/{created['id']}").json()["is_stale"] is True

    client.post(f"/applications/{created['id']}/notes", json={"note": "chased"})

    body = client.get(f"/applications/{created['id']}").json()
    assert (body["is_stale"], body["idle_days"]) == (False, 0)


# --- GET /applications/{id}/timeline --------------------------------------------------------


def test_timeline_lists_events_newest_first(client: TestClient, clock: FakeClock) -> None:
    created = create(client)
    clock.advance(days=1)
    client.post(f"/applications/{created['id']}/notes", json={"note": "emailed the recruiter"})
    clock.advance(days=1)
    apply_with_base(client, created["id"])

    response = client.get(f"/applications/{created['id']}/timeline")

    assert response.status_code == 200
    events = response.json()
    assert [(e["type"], e["from_stage"], e["to_stage"], e["note"]) for e in events] == [
        ("stage_change", "saved", "applied", None),
        ("note", None, None, "emailed the recruiter"),
        ("stage_change", None, "saved", None),
    ]
    times = [parse(e["created_at"]) for e in events]
    assert times == sorted(times, reverse=True)


def test_timeline_only_shows_events_of_that_application(client: TestClient) -> None:
    first = create(client, company="First")
    second = create(client, company="Second")
    client.post(f"/applications/{first['id']}/notes", json={"note": "only on first"})

    assert len(client.get(f"/applications/{first['id']}/timeline").json()) == 2
    assert len(client.get(f"/applications/{second['id']}/timeline").json()) == 1


def test_timeline_unknown_application_returns_404(client: TestClient) -> None:
    assert client.get("/applications/999/timeline").status_code == 404


def test_timeline_events_cannot_be_updated_or_deleted_through_the_api(client: TestClient) -> None:
    created = create(client)
    timeline = f"/applications/{created['id']}/timeline"
    event_id = client.get(timeline).json()[0]["id"]

    for method in ("put", "patch", "delete", "post"):
        assert getattr(client, method)(timeline).status_code == 405, method
    for method in ("get", "put", "patch", "delete"):
        assert getattr(client, method)(f"{timeline}/{event_id}").status_code == 404, method
    assert client.delete(f"/applications/{created['id']}/notes").status_code == 405


def test_new_endpoints_appear_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/applications/{application_id}/stage"]) == {"post"}
    assert set(paths["/applications/{application_id}/notes"]) == {"post"}
    assert set(paths["/applications/{application_id}/timeline"]) == {"get"}
    params = paths["/applications"]["get"]["parameters"]
    assert [p["name"] for p in params] == ["stage"]


# --- GET /applications ----------------------------------------------------------------------


def test_list_returns_items_counts_and_stale_count(client: TestClient) -> None:
    body = client.get("/applications").json()

    assert body == {"items": [], "counts_by_stage": dict.fromkeys(STAGES, 0), "stale_count": 0}
    assert list(body["counts_by_stage"]) == STAGES


def test_list_items_are_newest_first_and_carry_derived_fields(client: TestClient) -> None:
    first = create(client, company="First")
    second = create(client, company="Second")

    body = client.get("/applications").json()

    assert [a["id"] for a in body["items"]] == [second["id"], first["id"]]
    for item in body["items"]:
        assert {"allowed_next_stages", "last_activity_at", "is_stale", "idle_days"} <= set(item)


def test_stage_filter_narrows_items_but_not_the_counts(
    client: TestClient, clock: FakeClock
) -> None:
    a = create(client, company="A")
    b = create(client, company="B")
    create(client, company="C")
    apply_with_base(client, a["id"])
    apply_with_base(client, b["id"])
    move(client, b["id"], "rejected")
    clock.advance(days=20)

    everything = client.get("/applications").json()
    filtered = client.get("/applications", params={"stage": "applied"}).json()

    assert [i["company"] for i in filtered["items"]] == ["A"]
    assert len(everything["items"]) == 3
    expected = {**dict.fromkeys(STAGES, 0), "saved": 1, "applied": 1, "rejected": 1}
    assert filtered["counts_by_stage"] == expected
    assert everything["counts_by_stage"] == expected
    # A and C are stale (B is rejected). The filter does not change the count.
    assert filtered["stale_count"] == everything["stale_count"] == 2


def test_stage_filter_with_no_matches_returns_no_items(client: TestClient) -> None:
    create(client)

    body = client.get("/applications", params={"stage": "offer"}).json()

    assert body["items"] == []
    assert body["counts_by_stage"]["saved"] == 1


def test_stage_filter_rejects_an_unknown_stage(client: TestClient) -> None:
    assert client.get("/applications", params={"stage": "promoted"}).status_code == 422
