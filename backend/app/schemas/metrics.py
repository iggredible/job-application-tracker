from pydantic import BaseModel, Field

from app.models import AIFeature, Stage


class FunnelStep(BaseModel):
    stage: Stage
    count: int = Field(description="Applications that reached this stage, or a later one.")
    share_of_previous: float | None = Field(
        description="Share of the stage before that reached this one, from 0 to 1. Null for "
        "the first stage, and when the stage before is empty."
    )


class StageDuration(BaseModel):
    stage: Stage
    median_days: float | None = Field(
        description="Median days spent in the stage, from completed intervals only. Null when "
        "there are none."
    )
    sample_size: int = Field(description="How many completed intervals the median is over.")


class ResponseRate(BaseModel):
    applied: int
    responses: int = Field(
        description="Applications with a later stage change other than Withdrawn."
    )
    rate: float | None = Field(
        description="Responses over applied, from 0 to 1. Null when none applied."
    )


class ResumeComparison(BaseModel):
    """Response rate by the resume that was sent. A snapshot of the base resume counts as base.
    The groups are not comparable on their own: the user may tailor for better-fit jobs."""

    tailored: ResponseRate
    base: ResponseRate


class PipelineMetrics(BaseModel):
    """The job search, calculated on request from the timeline. Nothing here is stored."""

    total_applications: int
    applied_applications: int = Field(description="Applications that reached Applied.")
    funnel: list[FunnelStep]
    time_in_stage: list[StageDuration]
    response: ResponseRate
    stale_applications: int = Field(description="Applications with no activity in 14 or more days.")
    resume_comparison: ResumeComparison


class AIMetricsRow(BaseModel):
    """One feature, prompt version and model. Seeded calls have the model `seed`."""

    feature: AIFeature
    prompt_version: str
    model: str
    calls: int
    failed_calls: int
    approved_as_is: int
    edited_then_approved: int | None = Field(description="Null for a posting analysis.")
    rejected: int
    pending: int
    superseded: int = Field(description="Drafts left undecided while a newer one was made.")
    avg_edit_ratio: float | None = Field(
        description="Mean edit ratio of the approved drafts, 0 for unedited. Null for a posting "
        "analysis, and when none was approved."
    )
    avg_flags_per_draft: float | None = Field(
        description="Mean guardrail flags as generated per draft. Null for a posting analysis."
    )
    input_tokens: int
    output_tokens: int
    estimated_cost: float = Field(description="USD, summed from the cost stored with each call.")
    median_latency_ms: float


class AIMetrics(BaseModel):
    """The AI calls and what became of their output, calculated on request."""

    rows: list[AIMetricsRow]
