import time

from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect

VALID = {
    "company": "Northwind Freight",
    "role": "Senior Backend Engineer",
    "source": "linkedin",
    "posting_url": "https://northwind.example/careers/1",
    "posting_text": "Build services.",
}


def create(client: TestClient, **overrides) -> dict:
    response = client.post("/applications", json={**VALID, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_post_creates_application_and_returns_201(client: TestClient) -> None:
    response = client.post("/applications", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["stage"] == "saved"
    assert body["company"] == "Northwind Freight"
    assert body["source"] == "linkedin"
    assert body["created_at"]


def test_post_requires_company_role_source_and_posting_text(client: TestClient) -> None:
    for field in ("company", "role", "source", "posting_text"):
        payload = {k: v for k, v in VALID.items() if k != field}
        assert client.post("/applications", json=payload).status_code == 422, field

    for field in ("company", "role", "posting_text"):
        assert client.post("/applications", json={**VALID, field: "   "}).status_code == 422, field


def test_post_allows_missing_posting_url(client: TestClient) -> None:
    payload = {k: v for k, v in VALID.items() if k != "posting_url"}

    response = client.post("/applications", json=payload)

    assert response.status_code == 201
    assert response.json()["posting_url"] is None


def test_post_turns_blank_posting_url_into_null(client: TestClient) -> None:
    assert create(client, posting_url="  ")["posting_url"] is None


def test_post_rejects_non_http_posting_url(client: TestClient) -> None:
    response = client.post("/applications", json={**VALID, "posting_url": "javascript:alert(1)"})

    assert response.status_code == 422


def test_post_rejects_unknown_source(client: TestClient) -> None:
    assert client.post("/applications", json={**VALID, "source": "billboard"}).status_code == 422


def test_post_rejects_stage_in_body(client: TestClient) -> None:
    assert client.post("/applications", json={**VALID, "stage": "offer"}).status_code == 422


def test_get_list_returns_items_newest_first(client: TestClient) -> None:
    assert client.get("/applications").json()["items"] == []
    first = create(client, company="First")
    second = create(client, company="Second")

    response = client.get("/applications")

    assert response.status_code == 200
    assert [a["id"] for a in response.json()["items"]] == [second["id"], first["id"]]


def test_get_one_returns_application_and_404_when_missing(client: TestClient) -> None:
    created = create(client)

    assert client.get(f"/applications/{created['id']}").json() == created
    assert client.get("/applications/999").status_code == 404


def test_patch_changes_company_role_url_text_and_source(client: TestClient) -> None:
    created = create(client)
    changes = {
        "company": "Larkspur Health",
        "role": "Staff Engineer",
        "posting_url": "https://larkspur.example/jobs/9",
        "posting_text": "New text.",
        "source": "referral",
    }

    response = client.patch(f"/applications/{created['id']}", json=changes)

    assert response.status_code == 200
    body = response.json()
    for field, value in changes.items():
        assert body[field] == value
    assert body["stage"] == "saved"


def test_patch_partial_leaves_other_fields_unchanged(client: TestClient) -> None:
    created = create(client)

    body = client.patch(f"/applications/{created['id']}", json={"role": "Lead"}).json()

    assert body["role"] == "Lead"
    for field in ("company", "source", "posting_url", "posting_text", "stage"):
        assert body[field] == created[field]


def test_patch_cannot_change_stage(client: TestClient) -> None:
    created = create(client)

    response = client.patch(f"/applications/{created['id']}", json={"stage": "offer"})

    assert response.status_code == 422
    assert client.get(f"/applications/{created['id']}").json()["stage"] == "saved"


def test_patch_can_clear_posting_url(client: TestClient) -> None:
    created = create(client)

    response = client.patch(f"/applications/{created['id']}", json={"posting_url": None})

    assert response.status_code == 200
    assert response.json()["posting_url"] is None


def test_patch_rejects_blank_or_null_required_fields(client: TestClient) -> None:
    created = create(client)
    url = f"/applications/{created['id']}"

    for field in ("company", "role", "posting_text", "source"):
        assert client.patch(url, json={field: None}).status_code == 422, field
    for field in ("company", "role", "posting_text"):
        assert client.patch(url, json={field: "  "}).status_code == 422, field


def test_patch_with_empty_body_changes_nothing(client: TestClient) -> None:
    created = create(client)

    response = client.patch(f"/applications/{created['id']}", json={})

    assert response.status_code == 200
    assert response.json() == created


def test_patch_bumps_updated_at_not_created_at(client: TestClient) -> None:
    created = create(client)
    time.sleep(0.01)

    body = client.patch(f"/applications/{created['id']}", json={"role": "Lead"}).json()

    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] > created["updated_at"]


def test_post_and_patch_reject_fields_that_are_not_editable(client: TestClient) -> None:
    created = create(client)
    not_editable = {
        "id": 99,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "nonsense": 1,
    }

    for field, value in not_editable.items():
        assert client.post("/applications", json={**VALID, field: value}).status_code == 422, field
        response = client.patch(f"/applications/{created['id']}", json={field: value})
        assert response.status_code == 422, field

    assert client.get(f"/applications/{created['id']}").json() == created


def test_patch_unknown_id_returns_404(client: TestClient) -> None:
    assert client.patch("/applications/999", json={"role": "Lead"}).status_code == 404


def test_delete_is_not_allowed(client: TestClient) -> None:
    created = create(client)

    assert client.delete(f"/applications/{created['id']}").status_code == 405
    assert client.get(f"/applications/{created['id']}").status_code == 200


def test_endpoints_appear_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/applications"]) == {"get", "post"}
    assert set(paths["/applications/{application_id}"]) == {"get", "patch"}


def test_applications_table_has_only_the_documented_columns(test_engine: Engine) -> None:
    # submitted_resume_id arrived with feature 11 (migration 0009) and posting_tsv with
    # feature 12 (migration 0010), nothing else.
    columns = {c["name"] for c in inspect(test_engine).get_columns("applications")}

    assert columns == {
        "id", "company", "role", "posting_url", "posting_text",
        "source", "stage", "created_at", "updated_at", "submitted_resume_id", "posting_tsv",
    }  # fmt: skip


def test_the_search_column_never_reaches_the_api(client: TestClient) -> None:
    created = client.post("/applications", json=VALID).json()

    assert "posting_tsv" not in created
    assert "posting_tsv" not in client.get(f"/applications/{created['id']}").json()
    assert all("posting_tsv" not in row for row in client.get("/applications").json())


def test_stage_and_source_enums_have_the_documented_values(test_engine: Engine) -> None:
    enums = {e["name"]: e["labels"] for e in inspect(test_engine).get_enums()}

    assert enums["stage"] == [
        "saved", "applied", "screening", "interviewing",
        "offer", "accepted", "rejected", "withdrawn",
    ]  # fmt: skip
    assert enums["source"] == ["referral", "linkedin", "company_site", "recruiter", "other"]
