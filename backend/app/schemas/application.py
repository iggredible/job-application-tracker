from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import Source, Stage

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


class ApplicationRead(BaseModel):
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
