from datetime import datetime

from pydantic import BaseModel

from app.models import ReviewStatus
from app.schemas.coverage import ApplicationCoverageRead
from app.services.resume_review import Outcome


class GuardrailFlag(BaseModel):
    """A fact in the draft that the base resume does not support. `message` is shown as is."""

    field: str
    value: str
    message: str


class TailoredResumeRead(BaseModel):
    """What the Tailored resume section displays. Making a draft has no request body: everything
    the call needs is read from the application, its approved analysis and the base resume."""

    id: int
    application_id: int
    status: ReviewStatus
    prompt_version: str
    # How many past approved resumes were shown to the model as examples. Read from the AI call
    # on request, never stored on the resume.
    example_count: int
    content_markdown: str
    # The current flags, calculated on request from the text as it is now.
    guardrail_flags: list[GuardrailFlag]
    created_at: datetime
    reviewed_at: datetime | None
    # Calculated on request, never stored: what became of this resume, and whether the section
    # shows it (one per application).
    outcome: Outcome
    displayed: bool


class TailoredResumeEditRead(TailoredResumeRead):
    """A saved edit: the resume, and the coverage of its new text against the base resume."""

    coverage: ApplicationCoverageRead
