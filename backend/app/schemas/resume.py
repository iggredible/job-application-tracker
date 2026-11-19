from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import ReviewStatus


class ResumeWrite(BaseModel):
    """Only the text. The status and the owner are set by the service, never by the client."""

    model_config = ConfigDict(extra="forbid")

    content_markdown: str

    @field_validator("content_markdown")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # Checked without trimming: the text is stored exactly as typed.
        if not value.strip():
            raise ValueError("content_markdown cannot be blank")
        return value


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_markdown: str
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
