"""The timeline_events table: schema, the append-only trigger and the migration backfill."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError

INSERT_APPLICATION = text(
    """
    INSERT INTO applications (company, role, source, posting_text, created_at)
    VALUES (:company, 'Engineer', 'other', 'Text', :created_at)
    RETURNING id
    """
)


def insert_event(engine: Engine) -> tuple[int, int]:
    """One application with one note. Returns (application_id, event_id)."""
    with engine.begin() as conn:
        application_id = conn.execute(
            INSERT_APPLICATION, {"company": "Acme", "created_at": "2026-11-01T10:00:00Z"}
        ).scalar_one()
        event_id = conn.execute(
            text(
                "INSERT INTO timeline_events (application_id, type, note) "
                "VALUES (:id, 'note', 'hello') RETURNING id"
            ),
            {"id": application_id},
        ).scalar_one()
    return application_id, event_id


def test_timeline_events_table_has_the_documented_columns(test_engine: Engine) -> None:
    columns = {c["name"]: c for c in inspect(test_engine).get_columns("timeline_events")}

    assert set(columns) == {
        "id", "application_id", "type", "from_stage", "to_stage", "note", "created_at",
    }  # fmt: skip
    assert columns["application_id"]["nullable"] is False
    assert columns["type"]["nullable"] is False
    assert columns["created_at"]["nullable"] is False
    assert columns["from_stage"]["nullable"] and columns["to_stage"]["nullable"]
    assert columns["note"]["nullable"]


def test_event_type_enum_has_the_documented_values(test_engine: Engine) -> None:
    enums = {e["name"]: e["labels"] for e in inspect(test_engine).get_enums()}

    assert enums["event_type"] == ["stage_change", "note"]


def test_timeline_events_has_the_application_created_at_index(test_engine: Engine) -> None:
    indexes = inspect(test_engine).get_indexes("timeline_events")

    assert any(i["column_names"] == ["application_id", "created_at"] for i in indexes)


def test_timeline_events_reference_applications(test_engine: Engine) -> None:
    foreign_keys = inspect(test_engine).get_foreign_keys("timeline_events")

    assert [(f["constrained_columns"], f["referred_table"]) for f in foreign_keys] == [
        (["application_id"], "applications")
    ]


def test_trigger_rejects_update_on_timeline_events(test_engine: Engine) -> None:
    _, event_id = insert_event(test_engine)

    with pytest.raises(DBAPIError, match="append-only"), test_engine.begin() as conn:
        conn.execute(
            text("UPDATE timeline_events SET note = 'changed' WHERE id = :id"), {"id": event_id}
        )

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT note FROM timeline_events")).scalar_one() == "hello"


def test_trigger_rejects_delete_on_timeline_events(test_engine: Engine) -> None:
    _, event_id = insert_event(test_engine)

    with pytest.raises(DBAPIError, match="append-only"), test_engine.begin() as conn:
        conn.execute(text("DELETE FROM timeline_events WHERE id = :id"), {"id": event_id})

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM timeline_events")).scalar_one() == 1


def test_trigger_rejects_changing_the_stage_columns_too(test_engine: Engine) -> None:
    _, event_id = insert_event(test_engine)

    with pytest.raises(DBAPIError, match="append-only"), test_engine.begin() as conn:
        conn.execute(text("UPDATE timeline_events SET to_stage = 'offer'"))


def test_truncate_is_not_blocked(test_engine: Engine) -> None:
    insert_event(test_engine)

    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE timeline_events, applications RESTART IDENTITY CASCADE"))
        assert conn.execute(text("SELECT count(*) FROM timeline_events")).scalar_one() == 0


def test_migration_backfills_a_saved_event_for_existing_applications(
    test_engine: Engine, alembic_config: Config
) -> None:
    command.downgrade(alembic_config, "0002")
    try:
        with test_engine.begin() as conn:
            first = conn.execute(
                INSERT_APPLICATION, {"company": "First", "created_at": "2026-11-01T10:00:00Z"}
            ).scalar_one()
            second = conn.execute(
                INSERT_APPLICATION, {"company": "Second", "created_at": "2026-11-05T08:30:00Z"}
            ).scalar_one()

        command.upgrade(alembic_config, "head")

        with test_engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT e.application_id, e.type, e.from_stage, e.to_stage, e.note, "
                    "e.created_at = a.created_at "
                    "FROM timeline_events e JOIN applications a ON a.id = e.application_id "
                    "ORDER BY e.application_id"
                )
            ).all()
        assert rows == [
            (first, "stage_change", None, "saved", None, True),
            (second, "stage_change", None, "saved", None, True),
        ]
    finally:
        command.upgrade(alembic_config, "head")
