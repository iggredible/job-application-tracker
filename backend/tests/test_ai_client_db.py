"""AnthropicAIClient wired to the real DatabaseLogSink: what lands in the ai_calls table.

The other client tests use the in-memory sink; this file checks the same behavior end to end,
through the SDK stub into Postgres. The SDK is still the stub, so no network call is made.
"""

import json
from decimal import Decimal

import anthropic
import httpx2
import pytest
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.ai.client import AnthropicAIClient
from app.ai.prompts import RenderedPrompt
from app.ai.sinks import DatabaseLogSink
from app.ai.types import (
    AIAPIError,
    AIError,
    AIRefusalError,
    AITruncatedError,
    AIValidationError,
)
from app.core.config import ModelPrice
from app.models import AIFeature
from tests.fakes import StubAnthropic, make_message

PRICES = {"test-model": ModelPrice(input_per_mtok=Decimal("2"), output_per_mtok=Decimal("10"))}
PROMPT = RenderedPrompt(version="test-v1", system="Be brief.", user="Say hi.")
GOOD_JSON = json.dumps({"greeting": "hello"})


class Greeting(BaseModel):
    greeting: str


def client_for(sink: DatabaseLogSink, *outcomes: object) -> AnthropicAIClient:
    stub = StubAnthropic(*outcomes)  # type: ignore[arg-type]
    return AnthropicAIClient(stub, model="test-model", sink=sink, prices=PRICES)  # type: ignore[arg-type]


def generate(client: AnthropicAIClient, **kwargs: object):
    return client.generate(
        feature=AIFeature.TAILOR_RESUME, prompt=PROMPT, output_model=Greeting, **kwargs
    )


def insert_application(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO applications (company, role, source, posting_text) "
                "VALUES ('Acme', 'Engineer', 'other', 'Text') RETURNING id"
            )
        ).scalar_one()


def only_row(engine: Engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM ai_calls")).one()


def test_a_successful_call_writes_a_full_row_to_ai_calls(
    db_sink: DatabaseLogSink, test_engine: Engine
) -> None:
    application_id = insert_application(test_engine)
    client = client_for(db_sink, make_message(text=GOOD_JSON, input_tokens=1000, output_tokens=500))

    result = generate(client, application_id=application_id, retrieved_example_ids=[2, 8])

    row = only_row(test_engine)
    assert result.ai_call_id == row.id
    assert row.application_id == application_id
    assert (row.feature, row.prompt_version, row.model) == (
        "tailor_resume",
        "test-v1",
        "test-model",
    )
    assert row.request_json["system"] == "Be brief."
    assert row.request_json["messages"] == [{"role": "user", "content": "Say hi."}]
    assert "temperature" not in row.request_json
    assert row.response_json == {"greeting": "hello"}
    assert row.retrieved_example_ids == [2, 8]
    assert (row.input_tokens, row.output_tokens) == (1000, 500)
    assert row.estimated_cost == Decimal("0.007000")
    assert row.latency_ms >= 0
    assert row.schema_valid is True
    assert (row.stop_reason, row.error) == ("end_turn", None)


def api_error() -> Exception:
    return anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )


@pytest.mark.parametrize(
    ("outcome", "error_class", "kind", "stop_reason"),
    [
        pytest.param(api_error(), AIAPIError, "api_error", None, id="api-error"),
        pytest.param(
            make_message(stop_reason="refusal"), AIRefusalError, "refusal", "refusal", id="refusal"
        ),
        pytest.param(
            make_message(text='{"greeting": "he', stop_reason="max_tokens"),
            AITruncatedError,
            "truncated",
            "max_tokens",
            id="truncated",
        ),
        pytest.param(
            make_message(text='{"nope": 1}'),
            AIValidationError,
            "validation_error",
            "end_turn",
            id="validation-error",
        ),
    ],
)
def test_each_failure_type_writes_a_failed_row_to_ai_calls(
    outcome: object,
    error_class: type[AIError],
    kind: str,
    stop_reason: str | None,
    db_sink: DatabaseLogSink,
    test_engine: Engine,
) -> None:
    client = client_for(db_sink, outcome)

    with pytest.raises(error_class) as raised:
        generate(client)

    row = only_row(test_engine)
    assert raised.value.ai_call_id == row.id
    assert row.schema_valid is False
    assert row.response_json is None
    assert row.stop_reason == stop_reason
    assert row.error.startswith(f"{kind}:")


def test_a_failed_call_survives_a_rollback_in_the_caller(
    db_sink: DatabaseLogSink, db_session: Session, test_engine: Engine
) -> None:
    # A service starts a transaction, calls the model, the call fails and the service rolls back.
    db_session.execute(
        text(
            "INSERT INTO applications (company, role, source, posting_text) "
            "VALUES ('Rolled back', 'Engineer', 'other', 'Text')"
        )
    )
    client = client_for(db_sink, make_message(stop_reason="refusal"))

    with pytest.raises(AIRefusalError):
        generate(client)
    db_session.rollback()

    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM applications")).scalar_one() == 0
    assert only_row(test_engine).schema_valid is False
