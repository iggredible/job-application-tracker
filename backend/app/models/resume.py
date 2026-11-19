import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

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
    content_markdown: Mapped[str] = mapped_column(Text)
    status: Mapped[ReviewStatus] = mapped_column(
        enum_type(ReviewStatus, "review_status"),
        server_default=ReviewStatus.DRAFT.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
