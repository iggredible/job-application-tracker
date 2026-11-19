"""AnthropicAIClient: structured output, validation, the call log and the typed errors.

The SDK is replaced by StubAnthropic, which returns real SDK Message objects. The smoke script
(scripts/ai_smoke.py) checks the stub against the real API by hand.
"""

import asyncio
import json
from decimal import Decimal

import anthropic
import httpx2
import pytest
from pydantic import BaseModel, SecretStr

from app.ai.client import DEFAULT_MAX_TOKENS, AnthropicAIClient
from app.ai.prompts import RenderedPrompt
from app.ai.sinks import InMemoryLogSink
from app.ai.types import (
    AIAPIError,
    AIConfigurationError,
    AIError,
    AIRefusalError,
    AITruncatedError,
    AIValidationError,
)
from app.core.config import ModelPrice, Settings
from app.models import AIFeature
from tests.fakes import StubAnthropic, make_message

PRICES = {"test-model": ModelPrice(input_per_mtok=Decimal("2"), output_per_mtok=Decimal("10"))}
PROMPT = RenderedPrompt(version="test-v1", system="Be brief.", user="Say hi.")
GOOD_JSON = json.dumps({"greeting": "hello", "tags": ["a", "b"]})


class Greeting(BaseModel):
    greeting: str
    tags: list[str]


def build(
    *outcomes: object, model: str = "test-model"
) -> tuple[AnthropicAIClient, StubAnthropic, InMemoryLogSink]:
    stub = StubAnthropic(*outcomes)  # type: ignore[arg-type]
    sink = InMemoryLogSink()
    return AnthropicAIClient(stub, model=model, sink=sink, prices=PRICES), stub, sink


def generate(client: AnthropicAIClient, **kwargs: object):
    return client.generate(
        feature=AIFeature.POSTING_ANALYSIS, prompt=PROMPT, output_model=Greeting, **kwargs
    )


# --- success ---------------------------------------------------------------------------------


def test_a_successful_call_returns_the_validated_output_and_the_log_id() -> None:
    client, _, _ = build(make_message(text=GOOD_JSON, input_tokens=1000, output_tokens=500))

    result = generate(client)

    assert result.output == Greeting(greeting="hello", tags=["a", "b"])
    assert result.ai_call_id == 1


def test_a_successful_call_logs_a_full_row() -> None:
    client, stub, sink = build(make_message(text=GOOD_JSON, input_tokens=1000, output_tokens=500))

    generate(client, application_id=42, retrieved_example_ids=[7, 9])

    (record,) = sink.records
    assert record.application_id == 42
    assert record.feature is AIFeature.POSTING_ANALYSIS
    assert record.prompt_version == "test-v1"
    assert record.model == "test-model"
    assert record.request_json == stub.messages.calls[0]  # the full request, as sent
    assert record.response_json == {"greeting": "hello", "tags": ["a", "b"]}
    assert record.retrieved_example_ids == [7, 9]
    assert (record.input_tokens, record.output_tokens) == (1000, 500)
    assert record.estimated_cost == Decimal("0.007000")
    assert isinstance(record.latency_ms, int) and record.latency_ms >= 0
    assert record.schema_valid is True
    assert record.stop_reason == "end_turn"
    assert record.error is None


def test_a_successful_call_logs_exactly_one_row() -> None:
    client, _, sink = build(make_message(text=GOOD_JSON), make_message(text=GOOD_JSON))

    first, second = generate(client), generate(client)

    assert len(sink.records) == 2
    assert (first.ai_call_id, second.ai_call_id) == (1, 2)


def test_the_request_asks_for_structured_output_and_sets_no_temperature() -> None:
    client, stub, _ = build(make_message(text=GOOD_JSON))

    generate(client)

    (sent,) = stub.messages.calls
    assert sent["model"] == "test-model"
    assert sent["system"] == "Be brief."
    assert sent["messages"] == [{"role": "user", "content": "Say hi."}]
    assert sent["max_tokens"] == DEFAULT_MAX_TOKENS
    assert sent["output_config"] == {
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(Greeting)}
    }
    assert "temperature" not in sent


def test_max_tokens_can_be_overridden_per_call() -> None:
    client, stub, _ = build(make_message(text=GOOD_JSON))

    generate(client, max_tokens=64)

    assert stub.messages.calls[0]["max_tokens"] == 64


def test_an_unknown_model_logs_a_null_cost() -> None:
    client, _, sink = build(make_message(text=GOOD_JSON), model="not-in-the-table")

    generate(client)

    assert sink.records[0].estimated_cost is None
    assert sink.records[0].model == "not-in-the-table"


def test_a_thinking_block_before_the_answer_is_skipped() -> None:
    # The real API sends a reasoning block ahead of the text (seen in the smoke run).
    client, _, sink = build(make_message(text=GOOD_JSON, thinking="Let me think."))

    result = generate(client)

    assert result.output == Greeting(greeting="hello", tags=["a", "b"])
    assert sink.records[0].schema_valid is True


def test_a_cut_off_call_with_only_a_thinking_block_is_a_truncation() -> None:
    # Seen in the smoke run: a tiny max_tokens was used up by reasoning, so no text arrived.
    client, _, sink = build(make_message(thinking="Hmm", stop_reason="max_tokens"))

    with pytest.raises(AITruncatedError):
        generate(client)

    assert sink.records[0].stop_reason == "max_tokens"


# --- failures: each logs a row with schema_valid false, then raises a typed error ----------------


def assert_logged_failure(
    sink: InMemoryLogSink, error: AIError, *, kind: str, stop_reason: str | None
) -> None:
    (record,) = sink.records
    assert error.ai_call_id == 1
    assert record.schema_valid is False
    assert record.response_json is None
    assert record.stop_reason == stop_reason
    assert record.error is not None and record.error.startswith(f"{kind}:")
    assert isinstance(record.latency_ms, int)


def test_an_api_error_is_logged_and_raised() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client, _, sink = build(anthropic.APIConnectionError(request=request))

    with pytest.raises(AIAPIError) as raised:
        generate(client)

    assert_logged_failure(sink, raised.value, kind="api_error", stop_reason=None)
    assert sink.records[0].input_tokens is None and sink.records[0].estimated_cost is None


def test_an_api_status_error_is_logged_and_raised() -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(404, request=request, json={"error": {"message": "model: nope"}})
    client, _, sink = build(anthropic.NotFoundError("model: nope", response=response, body=None))

    with pytest.raises(AIAPIError) as raised:
        generate(client)

    assert_logged_failure(sink, raised.value, kind="api_error", stop_reason=None)
    assert "model: nope" in sink.records[0].error


def test_a_refusal_is_logged_and_raised() -> None:
    client, _, sink = build(make_message(stop_reason="refusal", output_tokens=3))

    with pytest.raises(AIRefusalError) as raised:
        generate(client)

    assert_logged_failure(sink, raised.value, kind="refusal", stop_reason="refusal")
    assert sink.records[0].output_tokens == 3  # the call was billed, so the tokens are logged


def test_output_cut_off_at_the_token_limit_is_logged_and_raised() -> None:
    client, _, sink = build(make_message(text='{"greeting": "he', stop_reason="max_tokens"))

    with pytest.raises(AITruncatedError) as raised:
        generate(client)

    assert_logged_failure(sink, raised.value, kind="truncated", stop_reason="max_tokens")


def test_the_stop_reason_is_checked_before_the_output_is_parsed() -> None:
    # The text happens to be valid JSON for the schema, but the call was cut off: it still fails.
    client, _, sink = build(make_message(text=GOOD_JSON, stop_reason="max_tokens"))

    with pytest.raises(AITruncatedError):
        generate(client)

    assert sink.records[0].schema_valid is False


def test_a_refusal_with_json_text_is_still_a_refusal() -> None:
    client, _, sink = build(make_message(text=GOOD_JSON, stop_reason="refusal"))

    with pytest.raises(AIRefusalError):
        generate(client)

    assert sink.records[0].schema_valid is False


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('{"greeting": "hello"}', id="missing-field"),
        pytest.param('{"greeting": 5, "tags": []}', id="wrong-type"),
        pytest.param("not json at all", id="not-json"),
        pytest.param("", id="no-content"),
    ],
)
def test_output_that_fails_validation_is_logged_and_raised(text: str) -> None:
    client, _, sink = build(make_message(text=text))

    with pytest.raises(AIValidationError) as raised:
        generate(client)

    assert_logged_failure(sink, raised.value, kind="validation_error", stop_reason="end_turn")
    assert (sink.records[0].input_tokens, sink.records[0].output_tokens) == (10, 20)


def test_every_failure_is_an_ai_error() -> None:
    for error in (AIAPIError, AIRefusalError, AITruncatedError, AIValidationError):
        assert issubclass(error, AIError)


def test_a_failed_call_does_not_stop_the_next_call_from_logging() -> None:
    client, _, sink = build(make_message(stop_reason="refusal"), make_message(text=GOOD_JSON))

    with pytest.raises(AIRefusalError):
        generate(client)
    result = generate(client)

    assert result.ai_call_id == 2
    assert [r.schema_valid for r in sink.records] == [False, True]


def test_the_error_log_is_bounded() -> None:
    client, _, sink = build(make_message(text="x" * 50_000))

    with pytest.raises(AIValidationError):
        generate(client)

    assert len(sink.records[0].error) <= 2000


# --- configuration -----------------------------------------------------------------------------


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_the_client_takes_the_model_and_key_from_settings() -> None:
    sink = InMemoryLogSink()

    client = AnthropicAIClient.from_settings(
        settings(anthropic_api_key=SecretStr("the-key"), anthropic_model="the-model"), sink
    )

    assert client.model == "the-model"
    assert client.sdk.api_key == "the-key"


def test_the_key_never_appears_in_the_logged_request() -> None:
    # Build the client the way production does, with a known key, then swap in the stub SDK.
    sink = InMemoryLogSink()
    client = AnthropicAIClient.from_settings(
        settings(anthropic_api_key=SecretStr("sk-test-secret-123"), anthropic_model="test-model"),
        sink,
    )
    assert client.sdk.api_key == "sk-test-secret-123"
    client.sdk = StubAnthropic(make_message(text=GOOD_JSON))  # type: ignore[assignment]

    generate(client)

    assert "sk-test-secret-123" not in json.dumps(sink.records[0].request_json)


@pytest.mark.parametrize(
    "values",
    [
        {"anthropic_api_key": SecretStr(""), "anthropic_model": "m"},
        {"anthropic_api_key": SecretStr("k"), "anthropic_model": ""},
    ],
)
def test_a_missing_key_or_model_is_a_configuration_error(values: dict[str, object]) -> None:
    with pytest.raises(AIConfigurationError):
        AnthropicAIClient.from_settings(settings(**values), InMemoryLogSink())


def test_a_configuration_error_is_not_an_ai_error() -> None:
    # No call was made, so there is no log row and no ai_call_id to carry.
    assert not issubclass(AIConfigurationError, AIError)


# --- the network guard -------------------------------------------------------------------------


def test_the_real_sdk_cannot_reach_the_network_in_tests() -> None:
    from tests.fakes import NetworkBlocked

    sdk = anthropic.Anthropic(api_key="not-a-real-key", max_retries=0)

    with pytest.raises(anthropic.APIConnectionError) as raised:
        sdk.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}])

    assert isinstance(raised.value.__cause__, NetworkBlocked)


def test_the_async_sdk_cannot_reach_the_network_in_tests() -> None:
    from tests.fakes import NetworkBlocked

    sdk = anthropic.AsyncAnthropic(api_key="not-a-real-key", max_retries=0)

    async def call() -> None:
        await sdk.messages.create(
            model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}]
        )

    with pytest.raises(anthropic.APIConnectionError) as raised:
        asyncio.run(call())

    assert isinstance(raised.value.__cause__, NetworkBlocked)
