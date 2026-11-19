"""The ai_calls table: columns, the enum, the index and the append-only trigger."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError

INSERT_CALL = text(
    """
    INSERT INTO ai_calls (feature, prompt_version, model, request_json, latency_ms, schema_valid)
    VALUES ('posting_analysis', 'v1', 'test-model', '{"system": "s"}', 12, true)
    RETURNING id
    """
)


def insert_call(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(INSERT_CALL).scalar_one()


def test_ai_calls_table_has_the_documented_columns(test_engine: Engine) -> None:
    columns = {c["name"]: c for c in inspect(test_engine).get_columns("ai_calls")}

    assert set(columns) == {
        "id", "application_id", "feature", "prompt_version", "model", "request_json",
        "response_json", "retrieved_example_ids", "input_tokens", "output_tokens",
        "estimated_cost", "latency_ms", "schema_valid", "stop_reason", "error", "created_at",
    }  # fmt: skip
    not_null = {"feature", "prompt_version", "model", "request_json", "retrieved_example_ids"}
    not_null |= {"latency_ms", "schema_valid", "created_at"}
    for name, column in columns.items():
        if name == "id":
            continue
        assert column["nullable"] is (name not in not_null), name


def test_ai_calls_column_types(test_engine: Engine) -> None:
    columns = {c["name"]: str(c["type"]) for c in inspect(test_engine).get_columns("ai_calls")}

    assert columns["request_json"] == "JSONB"
    assert columns["response_json"] == "JSONB"
    assert columns["retrieved_example_ids"] == "JSONB"
    assert columns["estimated_cost"] == "NUMERIC(10, 6)"
    assert columns["schema_valid"] == "BOOLEAN"


def test_ai_feature_enum_has_the_documented_values(test_engine: Engine) -> None:
    enums = {e["name"]: e["labels"] for e in inspect(test_engine).get_enums()}

    assert enums["ai_feature"] == ["posting_analysis", "tailor_resume"]


def test_ai_calls_has_the_application_index(test_engine: Engine) -> None:
    indexes = {i["name"]: i["column_names"] for i in inspect(test_engine).get_indexes("ai_calls")}

    assert indexes["ai_calls_application_idx"] == ["application_id"]


def test_ai_calls_reference_applications(test_engine: Engine) -> None:
    foreign_keys = inspect(test_engine).get_foreign_keys("ai_calls")

    assert [(f["constrained_columns"], f["referred_table"]) for f in foreign_keys] == [
        (["application_id"], "applications")
    ]


def test_retrieved_example_ids_defaults_to_an_empty_list(test_engine: Engine) -> None:
    insert_call(test_engine)

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT retrieved_example_ids FROM ai_calls")).scalar_one() == []


def test_trigger_rejects_update_on_ai_calls(test_engine: Engine) -> None:
    call_id = insert_call(test_engine)

    with pytest.raises(DBAPIError, match="append-only"), test_engine.begin() as conn:
        conn.execute(text("UPDATE ai_calls SET model = 'changed' WHERE id = :id"), {"id": call_id})

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT model FROM ai_calls")).scalar_one() == "test-model"


def test_trigger_rejects_delete_on_ai_calls(test_engine: Engine) -> None:
    call_id = insert_call(test_engine)

    with pytest.raises(DBAPIError, match="append-only"), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM ai_calls WHERE id = :id"), {"id": call_id})

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ai_calls")).scalar_one() == 1


def test_truncate_is_not_blocked_on_ai_calls(test_engine: Engine) -> None:
    insert_call(test_engine)

    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE ai_calls RESTART IDENTITY"))
        assert conn.execute(text("SELECT count(*) FROM ai_calls")).scalar_one() == 0
