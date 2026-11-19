from typing import NamedTuple

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.models import Application, PostingAnalysis, Resume, ReviewStatus


class ExampleRow(NamedTuple):
    """One candidate example: an approved tailored resume, and the keywords of its posting."""

    resume_id: int
    application_id: int
    keywords: list[str]
    content_markdown: str


class ExampleRepository:
    """The query behind example retrieval. It only reads: what to search for, how many to take
    and which application to leave out are decided by the caller."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query: str, *, exclude_application_id: int, limit: int) -> list[ExampleRow]:
        """Past applications whose posting matches `query` (PostgreSQL web search syntax), best
        match first, one row each: the application's most recently approved tailored resume.

        A tailored resume is one made by an AI call (`ai_call_id` is set). A base-resume snapshot
        has none, so it is never returned, and neither are drafts or rejected resumes. Equal
        ranks are ordered by the approval date and then the id, so the answer is repeatable.
        """
        tsquery = func.websearch_to_tsquery("english", query)
        newest = (
            select(Resume.id, Resume.content_markdown, Resume.reviewed_at)
            .where(
                Resume.application_id == Application.id,
                Resume.ai_call_id.is_not(None),
                Resume.status == ReviewStatus.APPROVED,
            )
            .order_by(Resume.reviewed_at.desc().nulls_last(), Resume.id.desc())
            .limit(1)
            .lateral("newest")
        )
        keywords = (
            select(PostingAnalysis.keywords)
            .where(
                PostingAnalysis.application_id == Application.id,
                PostingAnalysis.status == ReviewStatus.APPROVED,
            )
            .order_by(PostingAnalysis.created_at.desc(), PostingAnalysis.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            select(newest.c.id, Application.id, keywords, newest.c.content_markdown)
            .select_from(Application)
            .join(newest, true())
            .where(
                Application.id != exclude_application_id, Application.posting_tsv.op("@@")(tsquery)
            )
            .order_by(
                func.ts_rank(Application.posting_tsv, tsquery).desc(),
                newest.c.reviewed_at.desc().nulls_last(),
                newest.c.id.desc(),
            )
            .limit(limit)
        )
        return [
            ExampleRow(resume_id, application_id, list(found or []), markdown)
            for resume_id, application_id, found, markdown in self._session.execute(statement)
        ]
