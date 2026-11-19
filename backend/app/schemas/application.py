from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import EventType, ReviewStatus, Source, Stage
from app.services.submission import ResumeKind, StepKey, StepStatus

# Whitespace is trimmed and a blank value is rejected.
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _clean_posting_url(value: str | None) -> str | None:
    """Blank becomes None. Only http(s) links are kept: the value is rendered as a link."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError("posting_url must be an http or https URL")
    return value


class ApplicationCreate(BaseModel):
    """`stage` is deliberately absent. A new application starts in `saved`."""

    model_config = ConfigDict(extra="forbid")

    company: RequiredText
    role: RequiredText
    source: Source
    posting_url: str | None = None
    posting_text: RequiredText

    @model_validator(mode="after")
    def _clean_url(self) -> "ApplicationCreate":
        self.posting_url = _clean_posting_url(self.posting_url)
        return self


class ApplicationUpdate(BaseModel):
    """Only the fields that were sent change. `stage` is not editable here."""

    model_config = ConfigDict(extra="forbid")

    company: RequiredText | None = None
    role: RequiredText | None = None
    source: Source | None = None
    posting_url: str | None = None
    posting_text: RequiredText | None = None

    @model_validator(mode="after")
    def _validate(self) -> "ApplicationUpdate":
        for name in ("company", "role", "source", "posting_text"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if "posting_url" in self.model_fields_set:
            self.posting_url = _clean_posting_url(self.posting_url)
        return self


class ApplicationFields(BaseModel):
    """The columns of an application, as stored."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    role: str
    source: Source
    stage: Stage
    posting_url: str | None
    posting_text: str
    created_at: datetime
    updated_at: datetime


class SubmittedResumeRead(BaseModel):
    """The resume the application sent: a snapshot of the base resume, or a tailored resume."""

    id: int
    kind: ResumeKind
    created_at: datetime


class WorkflowStepRead(BaseModel):
    """One of the three steps on the detail page. The status and the line are the API's."""

    key: StepKey
    status: StepStatus
    text: str


class ApplicationRead(ApplicationFields):
    """The stored columns plus the values calculated on request."""

    allowed_next_stages: list[Stage]
    last_activity_at: datetime
    is_stale: bool
    idle_days: int
    submitted_resume: SubmittedResumeRead | None
    # When the application moved to Applied, from its timeline. Null before that.
    applied_at: datetime | None
    # Shown beside Change stage when a move from this stage happens elsewhere, else null.
    stage_change_hint: str | None
    steps: list[WorkflowStepRead]


class ApplicationList(BaseModel):
    """`counts_by_stage` and `stale_count` cover all applications, not only the filtered items."""

    items: list[ApplicationRead]
    counts_by_stage: dict[Stage, int]
    stale_count: int


class StageChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_stage: Stage


class ApplyRequest(BaseModel):
    """Which resume was sent. `choice` is optional here so a missing choice reaches the guard and
    is refused with a 409 and a message. `resume_id` is the tailored resume, for "tailored"."""

    model_config = ConfigDict(extra="forbid")

    choice: Literal["base", "tailored"] | None = None
    resume_id: int | None = None


class SubmittableResumeRead(BaseModel):
    """An option for "Which resume did you send?". A resume that cannot be sent is still listed,
    with the reason. `date` is when the base resume was last saved, or the tailored resume was
    decided (or made, while it is a draft)."""

    id: int
    kind: ResumeKind
    status: ReviewStatus
    date: datetime
    submittable: bool
    reason: str | None


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: RequiredText


class TimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    type: EventType
    from_stage: Stage | None
    to_stage: Stage | None
    note: str | None
    created_at: datetime
