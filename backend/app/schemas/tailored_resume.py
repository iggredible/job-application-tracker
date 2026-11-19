from datetime import datetime

from pydantic import BaseModel

from app.models import ReviewStatus


class TailoredResumeRead(BaseModel):
    """What the Tailored resume section displays. There is no request body: everything the call
    needs is read from the application, its approved analysis and the base resume."""

    id: int
    application_id: int
    status: ReviewStatus
    prompt_version: str
    content_markdown: str
    created_at: datetime
