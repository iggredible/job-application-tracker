import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Stage(enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Source(enum.Enum):
    REFERRAL = "referral"
    LINKEDIN = "linkedin"
    COMPANY_SITE = "company_site"
    RECRUITER = "recruiter"
    OTHER = "other"


def _enum_type(enum_class: type[enum.Enum], name: str) -> Enum:
    # Store the lowercase values, not the member names, to match the documented schema.
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda members: [m.value for m in members],
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    posting_url: Mapped[str | None] = mapped_column(Text)
    posting_text: Mapped[str] = mapped_column(Text)
    source: Mapped[Source] = mapped_column(_enum_type(Source, "source"))
    # Written only by ApplicationService.change_stage() (feature 3). The insert omits it, so
    # the server default applies.
    stage: Mapped[Stage] = mapped_column(_enum_type(Stage, "stage"), server_default=text("'saved'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
