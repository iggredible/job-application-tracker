"""The columns and trigger that feature 8 adds to resumes."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.test_resume_db import INSERT_BASE, insert_application

INSERT_DRAFT = text(
    "INSERT INTO resumes (application_id, content_markdown, draft_markdown, content_json) "
    "VALUES (:application_id, 'edited', 'generated', '{\"summary\": \"s\"}') RETURNING id"
)


def insert_draft(engine: Engine) -> int:
    application_id = insert_application(engine)
    with engine.begin() as conn:
        return conn.execute(INSERT_DRAFT, {"application_id": application_id}).scalar_one()


def test_the_new_columns_are_nullable_because_the_base_resume_has_none(
    test_engine: Engine,
) -> None:
    columns = {c["name"]: c for c in inspect(test_engine).get_columns("resumes")}

    for name in ("ai_call_id", "content_json", "draft_markdown"):
        assert columns[name]["nullable"] is True
    assert str(columns["content_json"]["type"]) == "JSONB"


def test_ai_call_id_is_a_foreign_key_to_ai_calls(test_engine: Engine) -> None:
    foreign_keys = inspect(test_engine).get_foreign_keys("resumes")

    assert any(
        fk["constrained_columns"] == ["ai_call_id"] and fk["referred_table"] == "ai_calls"
        for fk in foreign_keys
    )


def test_a_resume_cannot_point_at_a_missing_ai_call(test_engine: Engine) -> None:
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(text("INSERT INTO resumes (content_markdown, ai_call_id) VALUES ('x', 999)"))


def test_draft_markdown_cannot_be_changed_after_insert(test_engine: Engine) -> None:
    resume_id = insert_draft(test_engine)

    with pytest.raises(DBAPIError, match="draft_markdown"), test_engine.begin() as conn:
        conn.execute(
            text("UPDATE resumes SET draft_markdown = 'changed' WHERE id = :id"), {"id": resume_id}
        )

    with test_engine.connect() as conn:
        stored = conn.execute(text("SELECT draft_markdown FROM resumes")).scalar_one()
    assert stored == "generated"


def test_draft_markdown_cannot_be_cleared_or_set_later(test_engine: Engine) -> None:
    resume_id = insert_draft(test_engine)
    with test_engine.begin() as conn:
        base_id = conn.execute(INSERT_BASE, {"markdown": "base"}).scalar_one()

    with pytest.raises(DBAPIError, match="draft_markdown"), test_engine.begin() as conn:
        conn.execute(
            text("UPDATE resumes SET draft_markdown = NULL WHERE id = :id"), {"id": resume_id}
        )
    with pytest.raises(DBAPIError, match="draft_markdown"), test_engine.begin() as conn:
        conn.execute(
            text("UPDATE resumes SET draft_markdown = 'x' WHERE id = :id"), {"id": base_id}
        )


def test_other_columns_can_still_change(test_engine: Engine) -> None:
    resume_id = insert_draft(test_engine)

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE resumes SET content_markdown = 'again', status = 'approved' WHERE id = :id"
            ),
            {"id": resume_id},
        )
        row = conn.execute(text("SELECT content_markdown, status FROM resumes")).one()

    assert tuple(row) == ("again", "approved")
