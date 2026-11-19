"""Hand-run smoke test for the AI wrapper. It makes three real, tiny calls to Anthropic.

    cd backend && uv run python -m scripts.ai_smoke

Not part of `make test`: no test makes a network call. Its job is to prove that the stub in
tests/fakes.py matches the real API (stop reasons, usage fields, exception types).

It uses the in-memory log sink, never the app database. `ai_calls` is append-only, so rows
written here could not be removed. It needs ANTHROPIC_API_KEY and ANTHROPIC_MODEL (see .env).

Calls:
  1. success:     a small structured output          -> stop_reason end_turn, tokens, cost
  2. truncation:  max_tokens far too low             -> stop_reason max_tokens -> AITruncatedError
  3. API error:   a model name that does not exist   -> anthropic.NotFoundError -> AIAPIError
A refusal cannot be triggered on demand, so that case is covered by the stub only.
"""

import sys
from typing import Any

import anthropic
from pydantic import BaseModel

from app.ai.client import AnthropicAIClient
from app.ai.prompts import RenderedPrompt
from app.ai.sinks import InMemoryLogSink
from app.ai.types import AIAPIError, AIConfigurationError, AIError, AITruncatedError
from app.core.config import get_settings
from app.models import AIFeature


class Greeting(BaseModel):
    greeting: str
    tags: list[str]


SHORT = RenderedPrompt(
    version="smoke-v1",
    system="You answer in the requested JSON shape and nothing else.",
    user="Give a one-word greeting and exactly two short lowercase tags.",
)
LONG = RenderedPrompt(
    version="smoke-v1",
    system="You answer in the requested JSON shape and nothing else.",
    user="Give a greeting that is a full paragraph of at least 150 words, and two tags.",
)


class Recorder:
    """Wraps `sdk.messages.create` to keep the raw response or exception for comparison."""

    def __init__(self, sdk: anthropic.Anthropic) -> None:
        self.raw: Any = None
        original = sdk.messages.create

        def create(**kwargs: Any) -> Any:
            try:
                self.raw = original(**kwargs)
            except Exception as exc:
                self.raw = exc
                raise
            return self.raw

        sdk.messages.create = create  # type: ignore[method-assign]


def show(title: str, sink: InMemoryLogSink, recorder: Recorder) -> None:
    record = sink.records[-1]
    print(f"\n=== {title} ===")
    print(f"  logged id      : {len(sink.records)}")
    print(f"  schema_valid   : {record.schema_valid}")
    print(f"  stop_reason    : {record.stop_reason!r}")
    print(f"  tokens in/out  : {record.input_tokens} / {record.output_tokens}")
    print(f"  estimated_cost : {record.estimated_cost}")
    print(f"  latency_ms     : {record.latency_ms}")
    print(f"  response_json  : {record.response_json}")
    print(f"  error          : {record.error}")
    raw = recorder.raw
    if isinstance(raw, Exception):
        print(f"  raw SDK result : exception {type(raw).__module__}.{type(raw).__name__}")
    else:
        content_types = [block.type for block in raw.content]
        print(f"  raw SDK result : {type(raw).__name__}, content types {content_types}")
        print(f"  raw usage      : input={raw.usage.input_tokens} output={raw.usage.output_tokens}")


def main() -> int:
    settings = get_settings()
    sink = InMemoryLogSink()
    try:
        client = AnthropicAIClient.from_settings(settings, sink)
    except AIConfigurationError as exc:
        print(f"Not configured: {exc}. Set it in .env and run again.")
        return 2
    recorder = Recorder(client.sdk)
    print(f"Model: {client.model}")
    failures: list[str] = []

    def expect(condition: bool, what: str) -> None:
        print(f"  [{'ok' if condition else 'MISMATCH'}] {what}")
        if not condition:
            failures.append(what)

    # 1. success
    result = client.generate(
        feature=AIFeature.POSTING_ANALYSIS, prompt=SHORT, output_model=Greeting
    )
    show("1. success", sink, recorder)
    record = sink.records[-1]
    expect(result.ai_call_id == 1 and isinstance(result.output, Greeting), "returns output and id")
    expect(record.schema_valid and record.error is None, "logged as valid")
    expect(record.stop_reason == "end_turn", "stop_reason is 'end_turn'")
    expect(
        isinstance(record.input_tokens, int) and isinstance(record.output_tokens, int),
        "usage has integer input_tokens and output_tokens",
    )
    expect(
        record.estimated_cost is not None or client.model not in get_priced_models(),
        "cost is computed when the model is in the price table",
    )
    # A reasoning ("thinking") block can come before the answer, so look for a text block.
    expect("text" in [b.type for b in recorder.raw.content], "content has a text block")

    # 2. truncation
    try:
        client.generate(
            feature=AIFeature.POSTING_ANALYSIS, prompt=LONG, output_model=Greeting, max_tokens=16
        )
        expect(False, "a 16-token limit should have been cut off")
    except AITruncatedError:
        show("2. truncation (max_tokens=16)", sink, recorder)
        record = sink.records[-1]
        expect(record.stop_reason == "max_tokens", "stop_reason is 'max_tokens'")
        expect(not record.schema_valid and record.response_json is None, "logged as failed")
    except AIError as exc:
        show("2. truncation (max_tokens=16)", sink, recorder)
        expect(False, f"expected AITruncatedError, got {type(exc).__name__}: {exc}")

    # 3. API error (the model name does not exist)
    bad = AnthropicAIClient(client.sdk, model="claude-does-not-exist", sink=sink)
    try:
        bad.generate(feature=AIFeature.POSTING_ANALYSIS, prompt=SHORT, output_model=Greeting)
        expect(False, "an unknown model should have failed")
    except AIAPIError as exc:
        show("3. API error (unknown model)", sink, recorder)
        expect(isinstance(recorder.raw, anthropic.APIStatusError), "raw error is an APIStatusError")
        expect(
            isinstance(recorder.raw, anthropic.NotFoundError),
            f"raw error is a NotFoundError (got {type(recorder.raw).__name__})",
        )
        expect(exc.ai_call_id == len(sink.records), "error carries the log id")

    print()
    if failures:
        print(f"{len(failures)} mismatch(es) between the real API and what the stub assumes:")
        for what in failures:
            print(f"  - {what}")
        return 1
    print("All checks match: the stub's shapes are the real API's shapes.")
    return 0


def get_priced_models() -> set[str]:
    from app.core.config import MODEL_PRICES

    return set(MODEL_PRICES)


if __name__ == "__main__":
    sys.exit(main())
