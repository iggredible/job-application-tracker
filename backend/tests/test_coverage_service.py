"""CoverageService: which analysis and which resume are used, and the before/after comparison."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.ai.schemas import PostingAnalysisOutput, Requirement, RequirementCategory
from app.ai.sinks import DatabaseLogSink
from app.models import Resume, ReviewStatus
from app.repositories.applications import ApplicationRepository
from app.repositories.locks import GenerationLockRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate
from app.services.analysis import PostingAnalysisService
from app.services.applications import ApplicationNotFound, ApplicationService
from app.services.coverage import CoverageService, NoAnalysis, ResumeNotFound
from tests.conftest import FakeClock
from tests.fakes import FakeAIClient

BASE_TEXT = "Ruby on Rails and PostgreSQL. Led a small team."


def make_service(session: Session) -> CoverageService:
    return CoverageService(
        PostingAnalysisRepository(session),
        ApplicationRepository(session),
        ResumeRepository(session),
    )


def make_application(session: Session, company: str = "Northwind Freight") -> int:
    service = ApplicationService(
        ApplicationRepository(session),
        TimelineRepository(session),
        ResumeRepository(session),
        PostingAnalysisRepository(session),
    )
    created = service.create(
        ApplicationCreate(
            company=company,
            role="Senior Backend Engineer",
            source="linkedin",
            posting_text="Build services.",
        )
    )
    return created.application.id


def make_analysis(
    session: Session,
    sink: DatabaseLogSink,
    clock: FakeClock,
    application_id: int,
    keywords: list[str],
    decision: ReviewStatus = ReviewStatus.DRAFT,
) -> int:
    """Run the analysis service with a fake AI that returns these keywords, then decide it."""
    fake = FakeAIClient(
        sink,
        output=PostingAnalysisOutput(
            requirements=[Requirement(text="Anything", category=RequirementCategory.MUST_HAVE)],
            keywords=keywords,
        ),
    )
    service = PostingAnalysisService(
        PostingAnalysisRepository(session),
        ApplicationRepository(session),
        GenerationLockRepository(session),
        clock,
    )
    analysis_id = service.run(application_id, fake).analysis.id
    if decision is ReviewStatus.APPROVED:
        service.approve(analysis_id)
    elif decision is ReviewStatus.REJECTED:
        service.reject(analysis_id)
    clock.advance(minutes=1)
    return analysis_id


def save_base(session: Session, markdown: str = BASE_TEXT) -> int:
    resume = Resume(content_markdown=markdown, status=ReviewStatus.APPROVED)
    session.add(resume)
    session.commit()
    return resume.id


def save_resume_for(session: Session, application_id: int, markdown: str) -> int:
    resume = Resume(
        application_id=application_id, content_markdown=markdown, status=ReviewStatus.DRAFT
    )
    session.add(resume)
    session.commit()
    return resume.id


def count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


# --- Which analysis -----------------------------------------------------------------------------


def test_the_base_resume_is_used_by_default(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["ruby on rails", "react", "aws"])
    save_base(db_session)

    result = make_service(db_session).for_application(application_id)

    assert result.coverage.covered == ["ruby on rails"]
    assert result.coverage.missing == ["react", "aws"]
    assert result.coverage.ratio == pytest.approx(1 / 3)
    assert result.base is None
    assert result.newly_covered is None
    assert result.still_missing is None


def test_an_approved_analysis_is_used_over_a_newer_draft(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["postgresql"], ReviewStatus.APPROVED)
    make_analysis(db_session, db_sink, clock, application_id, ["react", "aws"])
    save_base(db_session)

    result = make_service(db_session).for_application(application_id)

    assert result.coverage.covered == ["postgresql"]
    assert result.coverage.missing == []


def test_the_latest_approved_analysis_is_used_when_there_are_several(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"], ReviewStatus.APPROVED)
    make_analysis(db_session, db_sink, clock, application_id, ["aws"], ReviewStatus.APPROVED)
    save_base(db_session)

    result = make_service(db_session).for_application(application_id)

    assert result.coverage.missing == ["aws"]


def test_the_latest_draft_is_used_when_none_is_approved(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"])
    make_analysis(db_session, db_sink, clock, application_id, ["postgresql", "aws"])
    save_base(db_session)

    result = make_service(db_session).for_application(application_id)

    assert result.coverage.covered == ["postgresql"]
    assert result.coverage.missing == ["aws"]


def test_a_rejected_analysis_is_never_used(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"], ReviewStatus.DRAFT)
    make_analysis(db_session, db_sink, clock, application_id, ["aws", "go"], ReviewStatus.REJECTED)
    save_base(db_session)

    result = make_service(db_session).for_application(application_id)

    assert result.coverage.missing == ["react"]


def test_only_rejected_analyses_means_no_analysis(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"], ReviewStatus.REJECTED)
    save_base(db_session)

    with pytest.raises(NoAnalysis):
        make_service(db_session).for_application(application_id)


def test_no_analysis_at_all_raises_no_analysis(db_session: Session) -> None:
    application_id = make_application(db_session)
    save_base(db_session)

    with pytest.raises(NoAnalysis):
        make_service(db_session).for_application(application_id)


def test_another_applications_analysis_is_not_used(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    mine = make_application(db_session)
    other = make_application(db_session, company="Other Co")
    make_analysis(db_session, db_sink, clock, other, ["react"], ReviewStatus.APPROVED)
    save_base(db_session)

    with pytest.raises(NoAnalysis):
        make_service(db_session).for_application(mine)


def test_an_unknown_application_raises_application_not_found(db_session: Session) -> None:
    save_base(db_session)

    with pytest.raises(ApplicationNotFound):
        make_service(db_session).for_application(999)


def test_an_analysis_with_no_keywords_gives_an_empty_zero_coverage(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, [])
    save_base(db_session)

    result = make_service(db_session).for_application(application_id)

    assert (result.coverage.covered, result.coverage.missing, result.coverage.ratio) == (
        [],
        [],
        0.0,
    )


# --- Which resume -------------------------------------------------------------------------------


def test_no_base_resume_raises_resume_not_found(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"])

    with pytest.raises(ResumeNotFound):
        make_service(db_session).for_application(application_id)


def test_a_resume_id_compares_that_resume_with_the_base(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(
        db_session,
        db_sink,
        clock,
        application_id,
        ["ruby on rails", "postgresql", "react", "aws"],
        ReviewStatus.APPROVED,
    )
    save_base(db_session, "Ruby on Rails and PostgreSQL.")
    tailored = save_resume_for(db_session, application_id, "Ruby on Rails, React and Kubernetes.")

    result = make_service(db_session).for_application(application_id, tailored)

    assert result.coverage.covered == ["ruby on rails", "react"]
    assert result.coverage.missing == ["postgresql", "aws"]
    assert result.coverage.ratio == 0.5
    assert result.base is not None
    assert result.base.covered == ["ruby on rails", "postgresql"]
    assert result.base.missing == ["react", "aws"]
    assert result.base.ratio == 0.5
    # Covered now but not in the base, and missing from both.
    assert result.newly_covered == ["react"]
    assert result.still_missing == ["aws"]


def test_a_keyword_the_resume_lost_is_neither_newly_covered_nor_still_missing(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["postgresql", "aws"])
    save_base(db_session, "PostgreSQL")
    tailored = save_resume_for(db_session, application_id, "Nothing relevant")

    result = make_service(db_session).for_application(application_id, tailored)

    assert result.coverage.missing == ["postgresql", "aws"]
    assert result.newly_covered == []
    assert result.still_missing == ["aws"]


def test_the_base_resume_id_gives_no_new_coverage(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["postgresql", "aws"])
    base_id = save_base(db_session)

    result = make_service(db_session).for_application(application_id, base_id)

    assert result.coverage == result.base
    assert result.newly_covered == []
    assert result.still_missing == ["aws"]


def test_an_unknown_resume_id_raises_resume_not_found(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"])
    save_base(db_session)

    with pytest.raises(ResumeNotFound):
        make_service(db_session).for_application(application_id, 999)


def test_a_resume_of_another_application_raises_resume_not_found(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    mine = make_application(db_session)
    other = make_application(db_session, company="Other Co")
    make_analysis(db_session, db_sink, clock, mine, ["react"])
    save_base(db_session)
    foreign = save_resume_for(db_session, other, "React")

    with pytest.raises(ResumeNotFound):
        make_service(db_session).for_application(mine, foreign)


def test_a_resume_id_without_a_base_resume_raises_resume_not_found(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react"])
    tailored = save_resume_for(db_session, application_id, "React")

    with pytest.raises(ResumeNotFound):
        make_service(db_session).for_application(application_id, tailored)


# --- Never stored -------------------------------------------------------------------------------


def test_calculating_coverage_writes_nothing(
    db_session: Session, db_sink: DatabaseLogSink, clock: FakeClock, test_engine: Engine
) -> None:
    application_id = make_application(db_session)
    make_analysis(db_session, db_sink, clock, application_id, ["react", "postgresql"])
    save_base(db_session)
    tables = ["applications", "posting_analyses", "resumes", "ai_calls", "timeline_events"]
    before = {table: count(test_engine, table) for table in tables}

    make_service(db_session).for_application(application_id)

    assert {table: count(test_engine, table) for table in tables} == before
    assert not db_session.new
    assert not db_session.dirty
