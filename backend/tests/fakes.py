"""Test doubles for the AI layer. No test makes a network call.

`StubAnthropic` stands in for the Anthropic SDK client and returns real SDK `Message` objects,
so the wrapper is tested against the SDK's own types. `FakeAIClient` stands in for the whole
`AIClient` and writes through the same log sink as production, so rows and foreign keys behave
the same way.
"""

from decimal import Decimal
from typing import Any

from anthropic.types import Message, TextBlock, ThinkingBlock, Usage
from pydantic import BaseModel

from app.ai.prompts import RenderedPrompt
from app.ai.types import AICallRecord, AIError, AIResult, LogSink
from app.models import AIFeature


class NetworkBlocked(Exception):
    """Raised by the autouse guard in conftest when a test tries to reach the network."""


def make_message(
    *,
    text: str = "",
    stop_reason: str = "end_turn",
    input_tokens: int | None = 10,
    output_tokens: int | None = 20,
    model: str = "test-model",
    thinking: str | None = None,
) -> Message:
    """A real SDK Message. An empty `text` gives no text block, as a refusal may. `thinking`
    adds the reasoning block the real API sends before the answer (seen in the smoke run)."""
    content: list[Any] = []
    if thinking is not None:
        content.append(ThinkingBlock(type="thinking", thinking=thinking, signature="sig"))
    if text:
        content.append(TextBlock(type="text", text=text))
    return Message(
        id="msg_test",
        content=content,
        model=model,
        role="assistant",
        stop_reason=stop_reason,
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def make_record(**overrides: Any) -> AICallRecord:
    """A complete, successful log record; override any field."""
    fields: dict[str, Any] = {
        "application_id": None,
        "feature": AIFeature.POSTING_ANALYSIS,
        "prompt_version": "test-v1",
        "model": "test-model",
        "request_json": {"system": "Be brief.", "messages": [{"role": "user", "content": "Hi"}]},
        "response_json": {"greeting": "hello"},
        "retrieved_example_ids": [],
        "input_tokens": 10,
        "output_tokens": 20,
        "estimated_cost": Decimal("0.000220"),
        "latency_ms": 123,
        "schema_valid": True,
        "stop_reason": "end_turn",
        "error": None,
    }
    return AICallRecord(**{**fields, **overrides})


class StubMessages:
    """`client.messages`: each create() call returns, or raises, the next queued outcome."""

    def __init__(self, outcomes: list[Message | Exception]) -> None:
        self._outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StubAnthropic:
    def __init__(self, *outcomes: Message | Exception) -> None:
        self.messages = StubMessages(list(outcomes))


class FakeAIClient:
    """Returns a canned output, or raises a canned `AIError`, after logging like production."""

    model = "fake-model"

    def __init__(
        self,
        sink: LogSink,
        *,
        output: BaseModel | None = None,
        error: type[AIError] | None = None,
    ) -> None:
        self.sink = sink
        self._output = output
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def generate[T: BaseModel](
        self,
        *,
        feature: AIFeature,
        prompt: RenderedPrompt,
        output_model: type[T],
        application_id: int | None = None,
        retrieved_example_ids: list[int] | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[T]:
        self.calls.append({"feature": feature, "prompt": prompt, "output_model": output_model})
        failed = self._error is not None
        ai_call_id = self.sink.write(
            AICallRecord(
                application_id=application_id,
                feature=feature,
                prompt_version=prompt.version,
                model=self.model,
                request_json={
                    "system": prompt.system,
                    "messages": [{"role": "user", "content": prompt.user}],
                },
                response_json=None
                if failed or self._output is None
                else self._output.model_dump(mode="json"),
                retrieved_example_ids=retrieved_example_ids or [],
                input_tokens=None,
                output_tokens=None,
                estimated_cost=None,
                latency_ms=0,
                schema_valid=not failed,
                stop_reason=None,
                error=f"fake: {self._error.__name__}" if self._error else None,
            )
        )
        if self._error is not None:
            raise self._error("fake failure", ai_call_id)
        assert isinstance(self._output, output_model)
        return AIResult(output=self._output, ai_call_id=ai_call_id)
