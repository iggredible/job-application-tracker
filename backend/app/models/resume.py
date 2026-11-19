import enum
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.ai_call import AICall
from app.models.base import Base, enum_type


class ReviewStatus(enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Resume(Base):
    """The base resume is the one row with no application (migration 0004 allows only one)."""

    __tablename__ = "resumes"
    __table_args__ = (
        Index("resumes_application_idx", "application_id"),
        Index(
            "resumes_one_base_idx",
            text("(true)"),
            unique=True,
            postgresql_where=text("application_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"))
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # the model's output
    # As generated. A database trigger rejects any change to it.
    draft_markdown: Mapped[str | None] = mapped_column(Text)
    content_markdown: Mapped[str] = mapped_column(Text)
    # The guardrail flags as generated (a list of {field, value, message}). Never changed.
    guardrail_flags: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    status: Mapped[ReviewStatus] = mapped_column(
        enum_type(ReviewStatus, "review_status"),
        server_default=ReviewStatus.DRAFT.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The prompt version is read from the call. Null for the base resume.
    ai_call: Mapped[AICall | None] = relationship(lazy="joined")
