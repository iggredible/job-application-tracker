"""Example retrieval against a real PostgreSQL database: the generated column and its index, the
ranking order, the exclusion rules and the empty case.

Rows are inserted with raw SQL so each test states exactly which past applications exist.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.repositories.examples import ExampleRepository
from app.services.retrieval import FullTextRetriever, RetrievedExample

DAY_1 = datetime(2026, 11, 1, tzinfo=UTC)
DAY_2 = datetime(2026, 11, 2, tzinfo=UTC)
DAY_3 = datetime(2026, 11, 3, tzinfo=UTC)

RAILS_POSTING = "Senior Ruby on Rails engineer. PostgreSQL, Kubernetes and REST APIs."


@dataclass
class Past:
    application_id: int
    resume_id: int | None


def add_call(engine: Engine, application_id: int) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO ai_calls (application_id, feature, prompt_version, model, "
                "request_json, latency_ms, schema_valid) "
                "VALUES (:app, 'tailor_resume', 'v1', 'm', '{}', 1, true) RETURNING id"
            ),
            {"app": application_id},
        ).scalar_one()


def add_application(engine: Engine, posting: str) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO applications (company, role, source, posting_text) "
                "VALUES ('Past Co', 'Engineer', 'other', :posting) RETURNING id"
            ),
            {"posting": posting},
        ).scalar_one()


def add_analysis(
    engine: Engine,
    application_id: int,
    keywords: list[str],
    *,
    status: str = "approved",
    created_at: datetime = DAY_1,
) -> None:
    call_id = add_call(engine, application_id)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO posting_analyses "
                "(application_id, ai_call_id, requirements, keywords, status, created_at) "
                "VALUES (:app, :call, '[]', CAST(:keywords AS jsonb), "
                "CAST(:status AS review_status), :created_at)"
            ),
            {
                "app": application_id,
                "call": call_id,
                "keywords": json.dumps(keywords),
                "status": status,
                "created_at": created_at,
            },
        )


def add_resume(
    engine: Engine,
    application_id: int,
    *,
    status: str = "approved",
    tailored: bool = True,
    reviewed_at: datetime | None = DAY_1,
    created_at: datetime = DAY_1,
    markdown: str = "# Past resume",
    generated: str = "# Generated",
) -> int:
    """A tailored resume has an AI call. A snapshot of the base resume has none."""
    call_id = add_call(engine, application_id) if tailored else None
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO resumes (application_id, ai_call_id, content_markdown, "
                "draft_markdown, status, reviewed_at, created_at) "
                "VALUES (:app, :call, :markdown, :generated, CAST(:status AS review_status), "
                ":reviewed_at, :created_at) RETURNING id"
            ),
            {
                "app": application_id,
                "call": call_id,
                "markdown": markdown,
                "generated": generated,
                "status": status,
                "reviewed_at": reviewed_at,
                "created_at": created_at,
            },
        ).scalar_one()


def past(
    engine: Engine,
    posting: str = RAILS_POSTING,
    *,
    keywords: list[str] | None = None,
    **resume: object,
) -> Past:
    """A past application with an approved analysis and, by default, an approved tailored resume."""
    application_id = add_application(engine, posting)
    add_analysis(engine, application_id, keywords or ["ruby on rails"])
    return Past(application_id, add_resume(engine, application_id, **resume))  # type: ignore[arg-type]


def find(
    session: Session, keywords: list[str], exclude_application_id: int = 0
) -> list[RetrievedExample]:
    return FullTextRetriever(ExampleRepository(session)).find(
        keywords, exclude_application_id=exclude_application_id
    )


def ids(found: list[RetrievedExample]) -> list[int]:
    return [example.resume_id for example in found]


# --- the column and its index -------------------------------------------------------------------


def test_posting_tsv_is_a_stored_generated_column(test_engine: Engine) -> None:
    with test_engine.connect() as conn:
        generated = conn.execute(
            text(
                "SELECT attgenerated FROM pg_attribute "
                "WHERE attrelid = 'applications'::regclass AND attname = 'posting_tsv'"
            )
        ).scalar_one()
        data_type = conn.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'applications' AND column_name = 'posting_tsv'"
            )
        ).scalar_one()

    assert generated == "s"  # stored
    assert data_type == "tsvector"


def test_posting_tsv_follows_the_posting_text(test_engine: Engine) -> None:
    application_id = add_application(test_engine, "We build Ruby on Rails services.")
    matches = text(
        "SELECT posting_tsv @@ websearch_to_tsquery('english', :q) FROM applications WHERE id = :id"
    )

    with test_engine.begin() as conn:
        assert conn.execute(matches, {"q": "rails", "id": application_id}).scalar_one() is True
        assert conn.execute(matches, {"q": "golang", "id": application_id}).scalar_one() is False
        conn.execute(
            text("UPDATE applications SET posting_text = 'We write Golang.' WHERE id = :id"),
            {"id": application_id},
        )
        assert conn.execute(matches, {"q": "golang", "id": application_id}).scalar_one() is True
        assert conn.execute(matches, {"q": "rails", "id": application_id}).scalar_one() is False


def test_posting_tsv_has_a_gin_index(test_engine: Engine) -> None:
    with test_engine.connect() as conn:
        definition = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'applications_posting_tsv_idx'")
        ).scalar_one()

    assert "USING gin (posting_tsv)" in definition


# --- ranking ------------------------------------------------------------------------------------


def test_matches_are_ranked_by_how_much_of_the_query_they_match(
    test_engine: Engine, db_session: Session
) -> None:
    # Created in the opposite order of their rank, so the order is not the id order.
    one = past(test_engine, "We use Kubernetes.")
    two = past(test_engine, "We use PostgreSQL and Kubernetes.")
    three = past(test_engine, "We use Ruby on Rails, PostgreSQL and Kubernetes.")

    found = find(db_session, ["ruby on rails", "postgresql", "kubernetes"])

    assert ids(found) == [three.resume_id, two.resume_id, one.resume_id]


def test_a_posting_matching_one_keyword_is_enough(test_engine: Engine, db_session: Session) -> None:
    # The keywords are OR-ed. With every term required, nothing would match here.
    only_postgres = past(test_engine, "We run PostgreSQL.")

    found = find(db_session, ["ruby on rails", "postgresql", "kubernetes", "react"])

    assert ids(found) == [only_postgres.resume_id]


def test_equal_matches_are_ordered_by_most_recently_approved_then_id(
    test_engine: Engine, db_session: Session
) -> None:
    oldest = past(test_engine, "We run PostgreSQL.", reviewed_at=DAY_1)
    newest = past(test_engine, "We run PostgreSQL.", reviewed_at=DAY_3)
    middle_a = past(test_engine, "We run PostgreSQL.", reviewed_at=DAY_2)
    middle_b = past(test_engine, "We run PostgreSQL.", reviewed_at=DAY_2)

    found = find(db_session, ["postgresql"])

    # Three of the four, the same answer every time.
    assert ids(found) == [newest.resume_id, middle_b.resume_id, middle_a.resume_id]
    assert oldest.resume_id not in ids(found)


def test_a_multi_word_keyword_matches_as_a_phrase_not_as_separate_words(
    test_engine: Engine, db_session: Session
) -> None:
    past(test_engine, "Machine operators who enjoy deep learning of safety rules.")
    phrase = past(test_engine, "We build machine learning systems.")

    found = find(db_session, ["machine learning"])

    assert ids(found) == [phrase.resume_id]


def test_only_the_top_three_are_returned(test_engine: Engine, db_session: Session) -> None:
    for number in range(4):
        past(
            test_engine,
            "We run PostgreSQL.",
            reviewed_at=datetime(2026, 11, 10 + number, tzinfo=UTC),
        )

    assert len(find(db_session, ["postgresql"])) == 3


# --- what is excluded ---------------------------------------------------------------------------


def test_the_application_being_tailored_is_excluded(
    test_engine: Engine, db_session: Session
) -> None:
    current = past(test_engine, "We run PostgreSQL.")
    other = past(test_engine, "We run PostgreSQL.")

    found = find(db_session, ["postgresql"], exclude_application_id=current.application_id)

    assert ids(found) == [other.resume_id]


@pytest.mark.parametrize(
    "resume",
    [
        pytest.param({"status": "draft", "reviewed_at": None}, id="a draft"),
        pytest.param({"status": "rejected"}, id="a rejected resume"),
        pytest.param({"tailored": False}, id="a base-resume snapshot"),
    ],
)
def test_only_approved_tailored_resumes_are_candidates(
    test_engine: Engine, db_session: Session, resume: dict
) -> None:
    past(test_engine, "We run PostgreSQL.", **resume)
    approved = past(test_engine, "We run PostgreSQL.")

    assert ids(find(db_session, ["postgresql"])) == [approved.resume_id]


def test_an_application_without_a_resume_or_without_a_match_is_not_a_candidate(
    test_engine: Engine, db_session: Session
) -> None:
    add_application(test_engine, "We run PostgreSQL.")  # no resume at all
    past(test_engine, "Embedded firmware in C.")  # a resume, but no keyword in its posting
    match = past(test_engine, "We run PostgreSQL.")

    assert ids(find(db_session, ["postgresql"])) == [match.resume_id]


def test_each_application_gives_its_most_recently_approved_resume_only(
    test_engine: Engine, db_session: Session
) -> None:
    application_id = add_application(test_engine, "We run PostgreSQL.")
    add_analysis(test_engine, application_id, ["postgresql"])
    add_resume(test_engine, application_id, reviewed_at=DAY_1, created_at=DAY_1)
    latest = add_resume(test_engine, application_id, reviewed_at=DAY_2, created_at=DAY_2)
    # Newer than both, but not approved: it neither replaces nor adds a candidate.
    add_resume(test_engine, application_id, status="draft", reviewed_at=None, created_at=DAY_3)

    found = find(db_session, ["postgresql"])

    assert ids(found) == [latest]


def test_a_base_resume_snapshot_does_not_hide_the_tailored_resume(
    test_engine: Engine, db_session: Session
) -> None:
    application_id = add_application(test_engine, "We run PostgreSQL.")
    add_analysis(test_engine, application_id, ["postgresql"])
    tailored = add_resume(test_engine, application_id, reviewed_at=DAY_1)
    add_resume(test_engine, application_id, tailored=False, reviewed_at=DAY_3)  # sent later

    assert ids(find(db_session, ["postgresql"])) == [tailored]


# --- what an example carries --------------------------------------------------------------------


def test_the_example_text_is_the_approved_text_not_the_generated_draft(
    test_engine: Engine, db_session: Session
) -> None:
    past(test_engine, "We run PostgreSQL.", markdown="# Edited by the user", generated="# Raw")

    (example,) = find(db_session, ["postgresql"])

    assert example.content_markdown == "# Edited by the user"


def test_the_label_keywords_are_the_latest_approved_analysis_of_that_application(
    test_engine: Engine, db_session: Session
) -> None:
    application_id = add_application(test_engine, "We run PostgreSQL.")
    add_analysis(test_engine, application_id, ["old"], created_at=DAY_1)
    add_analysis(test_engine, application_id, ["postgresql", "sidekiq"], created_at=DAY_2)
    add_analysis(test_engine, application_id, ["draft"], status="draft", created_at=DAY_3)
    add_analysis(test_engine, application_id, ["nope"], status="rejected", created_at=DAY_3)
    add_resume(test_engine, application_id)

    (example,) = find(db_session, ["postgresql"])

    assert example.application_id == application_id
    assert example.keywords == ["postgresql", "sidekiq"]


# --- the empty case -----------------------------------------------------------------------------


def test_no_past_applications_give_no_examples(db_session: Session) -> None:
    assert find(db_session, ["postgresql"]) == []


def test_no_matching_posting_gives_no_examples(test_engine: Engine, db_session: Session) -> None:
    past(test_engine, "Embedded firmware in C.")

    assert find(db_session, ["postgresql", "ruby on rails"]) == []


def test_no_keywords_give_no_examples(test_engine: Engine, db_session: Session) -> None:
    past(test_engine, "We run PostgreSQL.")

    assert find(db_session, []) == []


# --- raw keywords never break the search --------------------------------------------------------


def test_keywords_with_punctuation_are_searched_without_a_syntax_error(
    test_engine: Engine, db_session: Session
) -> None:
    match = past(test_engine, "We write C++ and run CI/CD pipelines.")

    found = find(db_session, ["c++", "ci/cd"])

    assert ids(found) == [match.resume_id]


@pytest.mark.parametrize(
    "keyword", ['say "hi"', "-foo", "or", "and", "(", ")", "a & b", "a | b", ":*", "'", "\\", "!"]
)
def test_search_syntax_in_a_keyword_is_treated_as_data(
    test_engine: Engine, db_session: Session, keyword: str
) -> None:
    past(test_engine, "We run PostgreSQL.")

    assert isinstance(find(db_session, [keyword]), list)  # no error, whatever it matches
