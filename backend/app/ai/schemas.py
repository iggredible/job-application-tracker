"""Output schemas for the LLM calls.

Limits such as lowercase, deduplication and the keyword cap are not part of these schemas.
Structured outputs support only part of JSON Schema, so code enforces them after parsing.
"""

import enum

from pydantic import BaseModel


class RequirementCategory(enum.Enum):
    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


class Requirement(BaseModel):
    text: str
    category: RequirementCategory


class PostingAnalysisOutput(BaseModel):
    requirements: list[Requirement]
    keywords: list[str]
