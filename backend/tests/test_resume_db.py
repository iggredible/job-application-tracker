"""The resumes table: columns, the enum and the single-base-resume rule."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

INSERT_BASE = text("INSERT INTO resumes (content_markdown) VALUES (:markdown) RETURNING id")


def insert_application(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO applications (company, role, source, posting_text) "
                "VALUES ('Acme', 'Engineer', 'other', 'Text') RETURNING id"
            )
        ).scalar_one()


def test_resumes_table_has_only_the_documented_columns(test_engine: Engine) -> None:
    columns = {c["name"]: c for c in inspect(test_engine).get_columns("resumes")}

    assert set(columns) == {
        "id", "application_id", "ai_call_id", "content_json", "draft_markdown",
        "content_markdown", "status", "created_at", "updated_at", "reviewed_at",
    }  # fmt: skip
    assert columns["application_id"]["nullable"] is True
    assert columns["content_markdown"]["nullable"] is False
    assert columns["status"]["nullable"] is False
    assert columns["created_at"]["nullable"] is False
    assert columns["updated_at"]["nullable"] is False
    assert columns["reviewed_at"]["nullable"] is True


def test_review_status_enum_has_the_documented_values(test_engine: Engine) -> None:
    enums = {e["name"]: e["labels"] for e in inspect(test_engine).get_enums()}

    assert enums["review_status"] == ["draft", "approved", "rejected"]


def test_resumes_are_indexed_by_application_id(test_engine: Engine) -> None:
    indexes = {i["name"]: i for i in inspect(test_engine).get_indexes("resumes")}

    assert indexes["resumes_application_idx"]["column_names"] == ["application_id"]


def test_a_second_base_resume_is_rejected_by_the_database(test_engine: Engine) -> None:
    with test_engine.begin() as conn:
        conn.execute(INSERT_BASE, {"markdown": "first"})

    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(INSERT_BASE, {"markdown": "second"})


def test_resumes_tied_to_applications_do_not_count_as_the_base_resume(
    test_engine: Engine,
) -> None:
    application_id = insert_application(test_engine)
    with test_engine.begin() as conn:
        conn.execute(INSERT_BASE, {"markdown": "base"})
        for markdown in ("one", "two"):
            conn.execute(
                text(
                    "INSERT INTO resumes (application_id, content_markdown) "
                    "VALUES (:application_id, :markdown)"
                ),
                {"application_id": application_id, "markdown": markdown},
            )

        count = conn.execute(text("SELECT count(*) FROM resumes")).scalar_one()

    assert count == 3


def test_a_resume_must_point_at_an_existing_application(test_engine: Engine) -> None:
    with pytest.raises(IntegrityError), test_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO resumes (application_id, content_markdown) VALUES (999999, 'orphan')")
        )
