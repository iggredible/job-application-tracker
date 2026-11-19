import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_type


class AIFeature(enum.Enum):
    POSTING_ANALYSIS = "posting_analysis"
    TAILOR_RESUME = "tailor_resume"


class AICall(Base):
    """One row per LLM call, failed calls included. Append-only: database triggers reject
    UPDATE and DELETE (migration 0005)."""

    __tablename__ = "ai_calls"
    __table_args__ = (Index("ai_calls_application_idx", "application_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    feature: Mapped[AIFeature] = mapped_column(enum_type(AIFeature, "ai_feature"))
    prompt_version: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSONB)  # the full rendered request
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # null when it failed
    retrieved_example_ids: Mapped[list[int]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))  # stored at call time
    latency_ms: Mapped[int] = mapped_column(Integer)
    schema_valid: Mapped[bool] = mapped_column(Boolean)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
