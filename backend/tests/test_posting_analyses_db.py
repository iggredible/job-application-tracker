"""The posting_analyses table: columns, foreign keys, the default status and the index."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError


def insert_application(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO applications (company, role, source, posting_text) "
                "VALUES ('Acme', 'Engineer', 'other', 'Text') RETURNING id"
            )
        ).scalar_one()


def insert_call(engine: Engine, application_id: int) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO ai_calls (application_id, feature, prompt_version, model, "
                "request_json, latency_ms, schema_valid) "
                "VALUES (:app, 'posting_analysis', 'v1', 'm', '{}', 1, true) RETURNING id"
            ),
            {"app": application_id},
        ).scalar_one()


INSERT_ANALYSIS = text(
    "INSERT INTO posting_analyses (application_id, ai_call_id, requirements, keywords) "
    "VALUES (:app, :call, '[]', '[]') RETURNING id"
)


def test_posting_analyses_table_has_the_documented_columns(test_engine: Engine) -> None:
    columns = {c["name"]: c for c in inspect(test_engine).get_columns("posting_analyses")}

    assert set(columns) == {
        "id", "application_id", "ai_call_id", "requirements", "keywords", "status",
        "created_at", "reviewed_at",
    }  # fmt: skip
    not_null = {"application_id", "ai_call_id", "requirements", "keywords", "status", "created_at"}
    for name, column in columns.items():
        if name == "id":
            continue
        assert column["nullable"] is (name not in not_null), name
    assert str(columns["requirements"]["type"]) == "JSONB"
    assert str(columns["keywords"]["type"]) == "JSONB"


def test_posting_analyses_are_indexed_by_application_id(test_engine: Engine) -> None:
    indexes = {i["name"]: i for i in inspect(test_engine).get_indexes("posting_analyses")}

    assert indexes["posting_analyses_application_idx"]["column_names"] == ["application_id"]


def test_posting_analyses_reference_applications_and_ai_calls(test_engine: Engine) -> None:
    foreign_keys = {
        fk["constrained_columns"][0]: fk["referred_table"]
        for fk in inspect(test_engine).get_foreign_keys("posting_analyses")
    }

    assert foreign_keys == {"application_id": "applications", "ai_call_id": "ai_calls"}


def test_a_new_analysis_defaults_to_draft_and_is_not_reviewed(test_engine: Engine) -> None:
    application_id = insert_application(test_engine)
    call_id = insert_call(test_engine, application_id)

    with test_engine.begin() as conn:
        analysis_id = conn.execute(INSERT_ANALYSIS, {"app": application_id, "call": call_id})
        row = conn.execute(
            text("SELECT status, reviewed_at, created_at FROM posting_analyses WHERE id = :id"),
            {"id": analysis_id.scalar_one()},
        ).one()

    assert row.status == "draft"
    assert row.reviewed_at is None
    assert row.created_at is not None


def test_an_analysis_needs_a_real_ai_call(test_engine: Engine) -> None:
    application_id = insert_application(test_engine)

    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(INSERT_ANALYSIS, {"app": application_id, "call": 999})
