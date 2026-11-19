"""FakeAIClient: canned output, but the same log sink as production."""

import enum
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.ai.prompts import RenderedPrompt
from app.ai.sinks import DatabaseLogSink
from app.ai.types import AIClient, AIRefusalError, AITruncatedError
from app.models import AIFeature
from tests.fakes import FakeAIClient

PROMPT = RenderedPrompt(version="fake-v1", system="System text", user="User text")


class Greeting(BaseModel):
    greeting: str


def insert_application(engine: Engine) -> int:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO applications (company, role, source, posting_text) "
                "VALUES ('Acme', 'Engineer', 'other', 'Text') RETURNING id"
            )
        ).scalar_one()


def generate(client: FakeAIClient, **kwargs: object):
    return client.generate(
        feature=AIFeature.TAILOR_RESUME, prompt=PROMPT, output_model=Greeting, **kwargs
    )


def test_the_fake_satisfies_the_ai_client_protocol(db_sink: DatabaseLogSink) -> None:
    assert isinstance(FakeAIClient(db_sink, output=Greeting(greeting="hi")), AIClient)


def test_the_fake_logs_a_real_row_and_returns_its_id(
    db_sink: DatabaseLogSink, test_engine: Engine
) -> None:
    application_id = insert_application(test_engine)
    client = FakeAIClient(db_sink, output=Greeting(greeting="hi"))

    result = generate(client, application_id=application_id, retrieved_example_ids=[4])

    assert result.output == Greeting(greeting="hi")
    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM ai_calls WHERE id = :id"), {"id": result.ai_call_id}
        ).one()
    assert row.application_id == application_id
    assert row.feature == "tailor_resume"
    assert row.prompt_version == "fake-v1"
    assert row.request_json["system"] == "System text"
    assert row.response_json == {"greeting": "hi"}
    assert row.retrieved_example_ids == [4]
    assert row.schema_valid is True


@pytest.mark.parametrize("error", [AITruncatedError, AIRefusalError])
def test_a_failing_fake_logs_a_failed_row_then_raises(
    error: type, db_sink: DatabaseLogSink, test_engine: Engine
) -> None:
    client = FakeAIClient(db_sink, error=error)

    with pytest.raises(error) as raised:
        generate(client)

    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM ai_calls")).one()
    assert raised.value.ai_call_id == row.id
    assert (row.schema_valid, row.response_json) == (False, None)


def test_foreign_keys_behave_as_in_production(db_sink: DatabaseLogSink) -> None:
    client = FakeAIClient(db_sink, output=Greeting(greeting="hi"))

    with pytest.raises(IntegrityError):
        generate(client, application_id=12345)


class Kind(enum.Enum):
    PHONE = "phone"


class Appointment(BaseModel):
    when: date
    kind: Kind
    price: Decimal


def test_the_fake_logs_json_like_production(db_sink: DatabaseLogSink, test_engine: Engine) -> None:
    # Dates, enums and decimals must be dumped in JSON mode, as the real client does, or the
    # fake would fail to write the row only in tests.
    output = Appointment(when=date(2026, 11, 19), kind=Kind.PHONE, price=Decimal("1.50"))
    client = FakeAIClient(db_sink, output=output)

    result = client.generate(
        feature=AIFeature.POSTING_ANALYSIS, prompt=PROMPT, output_model=Appointment
    )

    with test_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT response_json FROM ai_calls WHERE id = :id"), {"id": result.ai_call_id}
        ).scalar_one()
    assert stored == {"when": "2026-11-19", "kind": "phone", "price": "1.50"}


def test_the_fake_records_what_it_was_asked(db_sink: DatabaseLogSink) -> None:
    client = FakeAIClient(db_sink, output=Greeting(greeting="hi"))

    generate(client)

    assert client.calls[0]["prompt"] == PROMPT
    assert client.calls[0]["output_model"] is Greeting
