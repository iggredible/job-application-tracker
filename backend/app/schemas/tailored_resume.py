from datetime import datetime

from pydantic import BaseModel

from app.models import ReviewStatus


class GuardrailFlag(BaseModel):
    """A fact in the draft that the base resume does not support. `message` is shown as is."""

    field: str
    value: str
    message: str


class TailoredResumeRead(BaseModel):
    """What the Tailored resume section displays. There is no request body: everything the call
    needs is read from the application, its approved analysis and the base resume."""

    id: int
    application_id: int
    status: ReviewStatus
    prompt_version: str
    content_markdown: str
    # The current flags, calculated on request from the text as it is now.
    guardrail_flags: list[GuardrailFlag]
    created_at: datetime
