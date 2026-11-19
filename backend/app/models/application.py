import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_type


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


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    posting_url: Mapped[str | None] = mapped_column(Text)
    posting_text: Mapped[str] = mapped_column(Text)
    source: Mapped[Source] = mapped_column(enum_type(Source, "source"))
    # Written only by ApplicationService.change_stage() (feature 3). The insert omits it, so
    # the server default applies.
    stage: Mapped[Stage] = mapped_column(enum_type(Stage, "stage"), server_default=text("'saved'"))
    # The resume that was sent. Written only when the application moves Saved -> Applied, by
    # ApplicationService.change_stage() (feature 11). `use_alter` because resumes point back at
    # applications.
    submitted_resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", use_alter=True, name="applications_submitted_resume_id_fkey")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
