"""Example retrieval, the decisions: the query, the limit, the exclusion and the prompt text.

These tests use a fake repository, so they say nothing about SQL. `test_retrieval_db.py` runs the
same retriever against a real PostgreSQL database.
"""

from app.repositories.examples import ExampleRow
from app.services.retrieval import (
    MAX_EXAMPLES,
    ExampleRetriever,
    FullTextRetriever,
    RetrievedExample,
    build_search_query,
    format_examples,
)


class FakeExampleRepository:
    def __init__(self, rows: list[ExampleRow] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[dict] = []

    def search(self, query: str, *, exclude_application_id: int, limit: int) -> list[ExampleRow]:
        self.calls.append(
            {"query": query, "exclude_application_id": exclude_application_id, "limit": limit}
        )
        return self.rows


# --- build_search_query() -----------------------------------------------------------------------


def test_the_query_joins_the_keywords_with_or() -> None:
    assert build_search_query(["postgresql", "react"]) == '"postgresql" or "react"'


def test_a_multi_word_keyword_is_quoted_so_it_stays_a_phrase() -> None:
    assert build_search_query(["ruby on rails", "postgresql"]) == '"ruby on rails" or "postgresql"'


def test_a_keyword_that_looks_like_search_syntax_is_quoted_as_data() -> None:
    # Unquoted, "-foo" would exclude a word and a bare "or" would be the operator.
    assert build_search_query(["-foo", "or"]) == '"-foo" or "or"'


def test_a_quote_inside_a_keyword_cannot_end_the_phrase() -> None:
    assert build_search_query(['say "hi"']) == '"say hi"'


def test_blank_keywords_are_dropped_and_no_keywords_give_an_empty_query() -> None:
    assert build_search_query(["", "  ", '""', "react"]) == '"react"'
    assert build_search_query([]) == ""


# --- FullTextRetriever --------------------------------------------------------------------------


def test_the_retriever_asks_for_the_top_three_and_excludes_the_application() -> None:
    repository = FakeExampleRepository()

    FullTextRetriever(repository).find(["ruby on rails"], exclude_application_id=7)

    assert MAX_EXAMPLES == 3
    assert repository.calls == [
        {"query": '"ruby on rails"', "exclude_application_id": 7, "limit": 3}
    ]


def test_the_retriever_returns_the_rows_as_examples_in_the_order_given() -> None:
    repository = FakeExampleRepository(
        [
            ExampleRow(resume_id=9, application_id=2, keywords=["go"], content_markdown="# Two"),
            ExampleRow(resume_id=4, application_id=5, keywords=["ruby"], content_markdown="# One"),
        ]
    )

    found = FullTextRetriever(repository).find(["ruby"], exclude_application_id=1)

    assert found == [
        RetrievedExample(resume_id=9, application_id=2, keywords=["go"], content_markdown="# Two"),
        RetrievedExample(
            resume_id=4, application_id=5, keywords=["ruby"], content_markdown="# One"
        ),
    ]


def test_the_retriever_does_not_search_without_keywords() -> None:
    repository = FakeExampleRepository()

    assert FullTextRetriever(repository).find([], exclude_application_id=1) == []
    assert repository.calls == []


def test_the_full_text_retriever_is_an_example_retriever() -> None:
    # The tailoring service depends on the interface, so vector search can replace this class.
    retriever: ExampleRetriever = FullTextRetriever(FakeExampleRepository())

    assert retriever.find(["x"], exclude_application_id=1) == []


# --- format_examples() --------------------------------------------------------------------------


def test_no_examples_give_no_prompt_text() -> None:
    assert format_examples([]) == []


def test_the_examples_start_with_a_line_saying_they_are_not_a_source_of_facts() -> None:
    formatted = format_examples(
        [RetrievedExample(resume_id=1, application_id=2, keywords=["x"], content_markdown="# A")]
    )

    assert "style and emphasis only" in formatted[0]
    assert "not a source of facts" in formatted[0]


def test_each_example_is_labeled_with_its_postings_keywords() -> None:
    formatted = format_examples(
        [
            RetrievedExample(
                resume_id=1,
                application_id=2,
                keywords=["ruby on rails", "postgresql"],
                content_markdown="# First resume",
            ),
            RetrievedExample(
                resume_id=3, application_id=4, keywords=["go"], content_markdown="# Second resume"
            ),
        ]
    )

    assert len(formatted) == 3  # the notice, then one entry per example
    assert formatted[1] == "Example 1 (posting keywords: ruby on rails, postgresql)\n# First resume"
    assert formatted[2] == "Example 2 (posting keywords: go)\n# Second resume"
