from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload

from app.models import PostingAnalysis, ReviewStatus


class PostingAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, analysis: PostingAnalysis) -> PostingAnalysis:
        """Insert the row and flush so its id is available. The caller commits."""
        self._session.add(analysis)
        self._session.flush()
        return analysis

    def get(self, analysis_id: int) -> PostingAnalysis | None:
        return self._session.get(PostingAnalysis, analysis_id)

    def get_for_update(self, analysis_id: int) -> PostingAnalysis | None:
        """Read the row and lock it until this transaction ends, so a second decision on the
        same analysis waits instead of reading a stale status. The row is reloaded, so a
        decision that committed while this one waited is seen."""
        query = (
            select(PostingAnalysis)
            .where(PostingAnalysis.id == analysis_id)
            .with_for_update(of=PostingAnalysis)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(query)

    def list_for_application(self, application_id: int) -> list[PostingAnalysis]:
        """Newest first. Rows made at the same time are ordered by id."""
        query = (
            select(PostingAnalysis)
            .where(PostingAnalysis.application_id == application_id)
            .order_by(PostingAnalysis.created_at.desc(), PostingAnalysis.id.desc())
        )
        return list(self._session.scalars(query))

    def statuses_by_application(
        self, application_id: int | None = None
    ) -> dict[int, list[ReviewStatus]]:
        """The statuses of the analyses, newest first, by application: every application, or just
        `application_id`."""
        query = select(PostingAnalysis.application_id, PostingAnalysis.status).order_by(
            PostingAnalysis.created_at.desc(), PostingAnalysis.id.desc()
        )
        if application_id is not None:
            query = query.where(PostingAnalysis.application_id == application_id)
        statuses: dict[int, list[ReviewStatus]] = {}
        for owner, status in self._session.execute(query):
            statuses.setdefault(owner, []).append(status)
        return statuses

    def list_all(self) -> list[PostingAnalysis]:
        """Every analysis, for the metrics. The AI call is not loaded: the metrics read the
        calls themselves."""
        query = select(PostingAnalysis).options(lazyload(PostingAnalysis.ai_call))
        return list(self._session.scalars(query.order_by(PostingAnalysis.id)))

    def get_latest_approved(self, application_id: int) -> PostingAnalysis | None:
        query = (
            select(PostingAnalysis)
            .where(
                PostingAnalysis.application_id == application_id,
                PostingAnalysis.status == ReviewStatus.APPROVED,
            )
            .order_by(PostingAnalysis.created_at.desc(), PostingAnalysis.id.desc())
            .limit(1)
        )
        return self._session.scalar(query)

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    def refresh(self, analysis: PostingAnalysis) -> None:
        self._session.refresh(analysis)
