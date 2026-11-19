import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.application import Stage
from app.models.base import Base, enum_type


class EventType(enum.Enum):
    STAGE_CHANGE = "stage_change"
    NOTE = "note"


class TimelineEvent(Base):
    """Append-only. Database triggers reject UPDATE and DELETE (migration 0003)."""

    __tablename__ = "timeline_events"
    __table_args__ = (Index("timeline_events_application_idx", "application_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    type: Mapped[EventType] = mapped_column(enum_type(EventType, "event_type"))
    from_stage: Mapped[Stage | None] = mapped_column(enum_type(Stage, "stage"))
    to_stage: Mapped[Stage | None] = mapped_column(enum_type(Stage, "stage"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
