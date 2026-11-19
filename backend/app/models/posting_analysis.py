from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.ai_call import AICall
from app.models.base import Base, enum_type
from app.models.resume import ReviewStatus


class PostingAnalysis(Base):
    """What the LLM extracted from a posting. Every row starts as a draft; only the user's
    approve or reject changes the status. The prompt version is read from the AI call."""

    __tablename__ = "posting_analyses"
    __table_args__ = (Index("posting_analyses_application_idx", "application_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    ai_call_id: Mapped[int] = mapped_column(ForeignKey("ai_calls.id"))
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # [{text, category}]
    keywords: Mapped[list[str]] = mapped_column(JSONB)
    status: Mapped[ReviewStatus] = mapped_column(
        enum_type(ReviewStatus, "review_status"),
        server_default=ReviewStatus.DRAFT.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ai_call: Mapped[AICall] = relationship(lazy="joined")
