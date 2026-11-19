"""Example retrieval: find past approved tailored resumes with similar postings.

Before tailoring, the service asks an `ExampleRetriever` for up to three past resumes to show the
model as examples of style and emphasis. Nothing here calls the LLM, and the same keywords and
the same history always give the same examples.

`FullTextRetriever` searches with PostgreSQL full-text search. Another implementation, such as
vector search, can replace it without changing the tailoring service.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.repositories.examples import ExampleRepository

MAX_EXAMPLES = 3

NOTICE = (
    "These past resumes show style and emphasis only. They are not a source of facts. "
    "The base resume is the only source of facts."
)


@dataclass(frozen=True)
class RetrievedExample:
    """A past approved tailored resume. `keywords` are those of its posting's approved analysis."""

    resume_id: int
    application_id: int
    keywords: list[str]
    content_markdown: str


class ExampleRetriever(Protocol):
    def find(
        self, keywords: Sequence[str], *, exclude_application_id: int
    ) -> list[RetrievedExample]:
        """At most `MAX_EXAMPLES` examples, best match first, from any application but
        `exclude_application_id`. An empty list when nothing matches."""
        ...


def build_search_query(keywords: Sequence[str]) -> str:
    """The keywords as one PostgreSQL web search query: each one quoted, joined with `or`.

    A match on any keyword counts. Quoting keeps a multi-word keyword a phrase, and keeps a
    keyword such as `-foo` or `or` from being read as search syntax. A quote inside a keyword
    is dropped, since it would end the phrase. Blank keywords are skipped.
    """
    quoted = []
    for keyword in keywords:
        cleaned = " ".join(keyword.replace('"', " ").split())
        if cleaned:
            quoted.append(f'"{cleaned}"')
    return " or ".join(quoted)


def format_examples(examples: Sequence[RetrievedExample]) -> list[str]:
    """The text for the prompt's examples section: a line saying the examples are not a source
    of facts, then each example labeled with its posting's keywords. Nothing for no examples."""
    if not examples:
        return []
    entries = [
        f"Example {number} (posting keywords: {', '.join(example.keywords)})\n"
        f"{example.content_markdown}"
        for number, example in enumerate(examples, start=1)
    ]
    return [NOTICE, *entries]


class FullTextRetriever:
    def __init__(self, repository: ExampleRepository) -> None:
        self._repository = repository

    def find(
        self, keywords: Sequence[str], *, exclude_application_id: int
    ) -> list[RetrievedExample]:
        query = build_search_query(keywords)
        if not query:
            return []
        rows = self._repository.search(
            query, exclude_application_id=exclude_application_id, limit=MAX_EXAMPLES
        )
        return [
            RetrievedExample(row.resume_id, row.application_id, row.keywords, row.content_markdown)
            for row in rows
        ]
