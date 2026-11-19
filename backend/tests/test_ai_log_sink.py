"""The two log sinks. The database sink commits in its own transaction."""

from decimal import Decimal

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.sinks import DatabaseLogSink, InMemoryLogSink
from app.ai.types import LogSink
from app.models import AIFeature
from app.repositories.ai_calls import AICallRepository
from tests.fakes import make_record


def insert_application(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO applications (company, role, source, posting_text) "
                "VALUES ('Acme', 'Engineer', 'other', 'Text') RETURNING id"
            )
        ).scalar_one()


def test_the_sinks_satisfy_the_log_sink_protocol(db_sink: DatabaseLogSink) -> None:
    assert isinstance(db_sink, LogSink)
    assert isinstance(InMemoryLogSink(), LogSink)


def test_the_database_sink_writes_every_field_of_the_record(
    db_sink: DatabaseLogSink, test_engine: Engine
) -> None:
    application_id = insert_application(test_engine)
    record = make_record(
        application_id=application_id,
        feature=AIFeature.TAILOR_RESUME,
        retrieved_example_ids=[3, 5],
        estimated_cost=Decimal("0.123456"),
    )

    ai_call_id = db_sink.write(record)

    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM ai_calls WHERE id = :id"), {"id": ai_call_id}).one()
    assert row.application_id == application_id
    assert row.feature == "tailor_resume"
    assert row.prompt_version == "test-v1"
    assert row.model == "test-model"
    assert row.request_json == record.request_json
    assert row.response_json == {"greeting": "hello"}
    assert row.retrieved_example_ids == [3, 5]
    assert (row.input_tokens, row.output_tokens) == (10, 20)
    assert row.estimated_cost == Decimal("0.123456")
    assert row.latency_ms == 123
    assert row.schema_valid is True
    assert row.stop_reason == "end_turn"
    assert row.error is None
    assert row.created_at is not None


def test_the_database_sink_stores_a_failed_call(
    db_sink: DatabaseLogSink, test_engine: Engine
) -> None:
    record = make_record(
        response_json=None, schema_valid=False, stop_reason="max_tokens", error="truncated: cut"
    )

    ai_call_id = db_sink.write(record)

    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM ai_calls WHERE id = :id"), {"id": ai_call_id}).one()
    assert (row.response_json, row.schema_valid, row.error) == (None, False, "truncated: cut")


def test_the_log_row_survives_a_rollback_in_the_caller(
    db_sink: DatabaseLogSink, db_session: Session, test_engine: Engine
) -> None:
    # The caller's transaction has done work that is not committed yet.
    db_session.execute(
        text(
            "INSERT INTO applications (company, role, source, posting_text) "
            "VALUES ('Rolled back', 'Engineer', 'other', 'Text')"
        )
    )

    db_sink.write(make_record())
    db_session.rollback()

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ai_calls")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM applications")).scalar_one() == 0


def test_the_database_sink_does_not_touch_the_callers_session(
    db_sink: DatabaseLogSink, db_session: Session
) -> None:
    db_session.execute(text("SELECT 1"))
    transaction = db_session.get_transaction()

    db_sink.write(make_record())

    assert db_session.get_transaction() is transaction


def test_a_record_for_an_unknown_application_is_rejected_by_the_foreign_key(
    db_sink: DatabaseLogSink, test_engine: Engine
) -> None:
    with pytest.raises(IntegrityError):
        db_sink.write(make_record(application_id=999))

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ai_calls")).scalar_one() == 0


def test_the_repository_reads_back_what_was_written(
    db_sink: DatabaseLogSink, db_session: Session
) -> None:
    ai_call_id = db_sink.write(make_record())

    row = AICallRepository(db_session).get(ai_call_id)

    assert row is not None and row.id == ai_call_id
    assert row.feature is AIFeature.POSTING_ANALYSIS
    assert AICallRepository(db_session).get(ai_call_id + 1) is None


def test_the_in_memory_sink_keeps_records_and_numbers_them_from_one() -> None:
    sink = InMemoryLogSink()
    first, second = make_record(prompt_version="a"), make_record(prompt_version="b")

    ids = [sink.write(first), sink.write(second)]

    assert ids == [1, 2]
    assert sink.records == [first, second]


def test_the_in_memory_sink_never_touches_the_database(test_engine: Engine) -> None:
    InMemoryLogSink().write(make_record())

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ai_calls")).scalar_one() == 0
