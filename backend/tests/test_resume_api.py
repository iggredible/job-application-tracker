from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import FakeClock

RESUME = "# Jordan Avery\nLead Software Engineer\n\n## Skills\nRuby on Rails, PostgreSQL"


def count_rows(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM resumes")).scalar_one()


def test_get_returns_404_when_there_is_no_resume(client: TestClient) -> None:
    response = client.get("/resume")

    assert response.status_code == 404
    assert response.json() == {"detail": "resume not found"}


def test_put_creates_the_base_resume(client: TestClient) -> None:
    response = client.put("/resume", json={"content_markdown": RESUME})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] >= 1
    assert body["content_markdown"] == RESUME
    assert body["status"] == "approved"
    assert body["reviewed_at"] is None
    assert body["created_at"] and body["updated_at"]


def test_get_returns_the_saved_resume(client: TestClient) -> None:
    saved = client.put("/resume", json={"content_markdown": RESUME}).json()

    response = client.get("/resume")

    assert response.status_code == 200
    assert response.json() == saved


def test_put_replaces_the_text_and_moves_updated_at(
    client: TestClient, clock: FakeClock, test_engine: Engine
) -> None:
    first = client.put("/resume", json={"content_markdown": RESUME}).json()
    clock.advance(hours=1)

    second = client.put("/resume", json={"content_markdown": "# Jordan Avery v2"})

    assert second.status_code == 200
    body = second.json()
    assert body["id"] == first["id"]
    assert body["content_markdown"] == "# Jordan Avery v2"
    assert body["created_at"] == first["created_at"]
    assert body["updated_at"] > first["updated_at"]
    assert client.get("/resume").json()["content_markdown"] == "# Jordan Avery v2"
    assert count_rows(test_engine) == 1


def test_the_base_resume_stays_approved_after_a_replace(client: TestClient) -> None:
    client.put("/resume", json={"content_markdown": RESUME})

    body = client.put("/resume", json={"content_markdown": "changed"}).json()

    assert body["status"] == "approved"


def test_put_rejects_blank_content(client: TestClient, test_engine: Engine) -> None:
    for blank in ("", "   ", "\n\n"):
        response = client.put("/resume", json={"content_markdown": blank})

        assert response.status_code == 422
    assert count_rows(test_engine) == 0


def test_a_blank_put_does_not_overwrite_the_saved_resume(client: TestClient) -> None:
    client.put("/resume", json={"content_markdown": RESUME})

    response = client.put("/resume", json={"content_markdown": " "})

    assert response.status_code == 422
    assert client.get("/resume").json()["content_markdown"] == RESUME


def test_put_rejects_a_missing_body_field(client: TestClient) -> None:
    assert client.put("/resume", json={}).status_code == 422


def test_put_rejects_fields_the_client_may_not_set(client: TestClient) -> None:
    for extra in ({"status": "draft"}, {"application_id": 1}, {"reviewed_at": "2026-11-18"}):
        response = client.put("/resume", json={"content_markdown": RESUME, **extra})

        assert response.status_code == 422


def test_the_resume_endpoints_are_in_the_openapi_schema(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/resume"]) == {"get", "put"}
