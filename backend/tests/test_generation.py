"""analyze(): the pure function that makes the posting analysis call.

It touches no database: the tests give it an in-memory log sink.
"""

import pytest

from app.ai.schemas import PostingAnalysisOutput, Requirement, RequirementCategory
from app.ai.sinks import InMemoryLogSink
from app.ai.types import (
    AIAPIError,
    AIError,
    AIRefusalError,
    AITruncatedError,
    AIValidationError,
)
from app.models import AIFeature
from app.services.generation import MAX_KEYWORDS, analyze
from tests.fakes import FakeAIClient


def must(text: str) -> Requirement:
    return Requirement(text=text, category=RequirementCategory.MUST_HAVE)


def run(output: PostingAnalysisOutput, sink: InMemoryLogSink | None = None):
    sink = sink or InMemoryLogSink()
    return analyze(FakeAIClient(sink, output=output), posting_text="A posting.", application_id=7)


def test_analyze_makes_one_posting_analysis_call_and_logs_it() -> None:
    sink = InMemoryLogSink()
    client = FakeAIClient(sink, output=PostingAnalysisOutput(requirements=[], keywords=["go"]))

    result = analyze(client, posting_text="Build services.", application_id=7)

    assert result.ai_call_id == 1
    assert len(client.calls) == 1
    assert client.calls[0]["feature"] is AIFeature.POSTING_ANALYSIS
    assert client.calls[0]["output_model"] is PostingAnalysisOutput
    assert len(sink.records) == 1
    record = sink.records[0]
    assert (record.application_id, record.prompt_version) == (7, "v1")
    assert "<posting>\nBuild services.\n</posting>" in record.request_json["messages"][0]["content"]


def test_keywords_are_lowercased_and_trimmed() -> None:
    output = PostingAnalysisOutput(requirements=[], keywords=["Ruby on Rails ", " PostgreSQL"])

    assert run(output).output.keywords == ["ruby on rails", "postgresql"]


def test_keywords_are_deduplicated_after_lowercasing_and_keep_their_order() -> None:
    output = PostingAnalysisOutput(
        requirements=[], keywords=["PostgreSQL", "react", "postgresql", "React", "aws"]
    )

    assert run(output).output.keywords == ["postgresql", "react", "aws"]


def test_blank_keywords_are_dropped() -> None:
    output = PostingAnalysisOutput(requirements=[], keywords=["aws", "", "   ", "react"])

    assert run(output).output.keywords == ["aws", "react"]


def test_keywords_are_capped_at_25_by_trimming_the_extras() -> None:
    keywords = [f"skill {n}" for n in range(30)]

    result = run(PostingAnalysisOutput(requirements=[], keywords=keywords))

    assert MAX_KEYWORDS == 25
    assert result.output.keywords == keywords[:25]


def test_duplicates_do_not_use_up_the_cap() -> None:
    keywords = ["Go", "go"] * 5 + [f"skill {n}" for n in range(30)]

    result = run(PostingAnalysisOutput(requirements=[], keywords=keywords))

    assert result.output.keywords == ["go", *[f"skill {n}" for n in range(24)]]


def test_requirements_are_trimmed_and_blank_ones_dropped() -> None:
    output = PostingAnalysisOutput(
        requirements=[
            must("  PostgreSQL  "),
            must("   "),
            Requirement(text="React", category=RequirementCategory.NICE_TO_HAVE),
        ],
        keywords=[],
    )

    requirements = run(output).output.requirements

    assert [(r.text, r.category.value) for r in requirements] == [
        ("PostgreSQL", "must_have"),
        ("React", "nice_to_have"),
    ]


def test_the_log_keeps_what_the_model_returned_and_the_result_is_the_trimmed_version() -> None:
    sink = InMemoryLogSink()
    output = PostingAnalysisOutput(requirements=[], keywords=["AWS", "aws"])

    result = run(output, sink)

    assert sink.records[0].response_json["keywords"] == ["AWS", "aws"]
    assert result.output.keywords == ["aws"]


@pytest.mark.parametrize("error", [AIAPIError, AIRefusalError, AITruncatedError, AIValidationError])
def test_a_failed_call_is_logged_and_raises_the_typed_error(error: type[AIError]) -> None:
    sink = InMemoryLogSink()
    client = FakeAIClient(sink, error=error)

    with pytest.raises(error) as raised:
        analyze(client, posting_text="A posting.", application_id=7)

    assert raised.value.ai_call_id == 1
    assert len(sink.records) == 1
    assert sink.records[0].schema_valid is False
    assert sink.records[0].response_json is None
