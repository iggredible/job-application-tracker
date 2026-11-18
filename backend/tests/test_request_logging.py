import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RequestLoggingMiddleware


def test_request_logging_emits_json_line_and_request_id_header(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert request_id

    lines = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["request_id"] == request_id
    assert entry["method"] == "GET"
    assert entry["path"] == "/health"
    assert entry["status_code"] == 200
    assert isinstance(entry["latency_ms"], int | float)
    assert entry["latency_ms"] >= 0


def test_unhandled_error_still_logs_one_line_and_returns_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO):
        response = client.get("/boom")

    assert response.status_code == 500
    request_id = response.headers["X-Request-ID"]

    lines = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["request_id"] == request_id
    assert entry["status_code"] == 500

    # The traceback is not swallowed: it goes to its own logger.
    errors = [r for r in caplog.records if r.name == "app.error"]
    assert len(errors) == 1
    assert errors[0].exc_info is not None


def test_request_ids_differ_between_requests(client: TestClient) -> None:
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]

    assert first != second
