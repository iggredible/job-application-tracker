from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.applications import get_clock
from app.core.clock import Clock
from app.core.db import get_session
from app.repositories.ai_calls import AICallRepository
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.metrics import AIMetrics, PipelineMetrics
from app.services.metrics import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


def get_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> MetricsService:
    return MetricsService(
        ApplicationRepository(session),
        TimelineRepository(session),
        ResumeRepository(session),
        PostingAnalysisRepository(session),
        AICallRepository(session),
        clock,
    )


@router.get("/pipeline", response_model=PipelineMetrics)
def pipeline_metrics(service: MetricsService = Depends(get_service)) -> PipelineMetrics:
    """The job search: the funnel, time in each stage, response rate, stale applications and
    tailored vs base resume. Calculated now from the timeline and never stored.

    "Reached a stage" is read from the timeline, not from the current stage. The tailored vs
    base comparison is confounded, because tailoring may go to better-fit jobs.
    """
    return service.pipeline()  # type: ignore[return-value]  # validated from the dataclass


@router.get("/ai", response_model=AIMetrics)
def ai_metrics(service: MetricsService = Depends(get_service)) -> AIMetrics:
    """The AI calls, one row per feature, prompt version and model, so seeded calls (model
    `seed`) stay apart from real ones. Calculated now from the call log and the drafts the
    calls produced, and never stored."""
    return service.ai()  # type: ignore[return-value]  # validated from the dataclass
