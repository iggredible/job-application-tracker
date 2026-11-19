from datetime import datetime

from pydantic import BaseModel

from app.ai.schemas import RequirementCategory
from app.models import ReviewStatus


class RequirementRead(BaseModel):
    text: str
    category: RequirementCategory


class AnalysisRead(BaseModel):
    """What the card displays. There is no request body: the posting text is read from the
    application, and the status is changed only by the approve and reject endpoints."""

    id: int
    application_id: int
    status: ReviewStatus
    prompt_version: str
    requirements: list[RequirementRead]
    keywords: list[str]
    created_at: datetime
    reviewed_at: datetime | None
