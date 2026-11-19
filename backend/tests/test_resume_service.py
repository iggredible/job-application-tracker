import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Resume, ReviewStatus
from app.repositories.resumes import ResumeRepository
from app.services.resumes import ResumeNotFound, ResumeService
from tests.conftest import FakeClock


def make_service(session: Session, clock: FakeClock) -> ResumeService:
    return ResumeService(ResumeRepository(session), clock)


def count_rows(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Resume))


def test_get_base_raises_when_no_resume_exists(db_session: Session, clock: FakeClock) -> None:
    with pytest.raises(ResumeNotFound):
        make_service(db_session, clock).get_base()


def test_the_first_save_creates_an_approved_base_resume(
    db_session: Session, clock: FakeClock
) -> None:
    resume = make_service(db_session, clock).save_base("# Jordan Avery")

    assert resume.id is not None
    assert resume.application_id is None
    assert resume.content_markdown == "# Jordan Avery"
    assert resume.status is ReviewStatus.APPROVED
    assert resume.reviewed_at is None
    assert resume.created_at == clock.now
    assert resume.updated_at == clock.now


def test_a_second_save_replaces_the_text_in_place(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    first = service.save_base("# Jordan Avery")
    first_id, created_at = first.id, first.created_at
    clock.advance(hours=2)

    second = service.save_base("# Jordan Avery\n\n## Skills")

    assert second.id == first_id
    assert second.content_markdown == "# Jordan Avery\n\n## Skills"
    assert second.created_at == created_at
    assert second.updated_at == clock.now
    assert second.updated_at > second.created_at


def test_saving_twice_leaves_exactly_one_row(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)

    service.save_base("one")
    service.save_base("two")

    assert count_rows(db_session) == 1
    assert service.get_base().content_markdown == "two"


def test_a_save_that_loses_a_race_replaces_the_row_the_other_save_created(
    db_session: Session, clock: FakeClock
) -> None:
    make_service(db_session, clock).save_base("created by the other request")

    class StaleRepository(ResumeRepository):
        """The first lookup misses, as if the other request had not committed yet."""

        missed = False

        def get_base(self) -> Resume | None:
            if not self.missed:
                self.missed = True
                return None
            return super().get_base()

    clock.advance(minutes=1)
    resume = ResumeService(StaleRepository(db_session), clock).save_base("mine")

    assert resume.content_markdown == "mine"
    assert resume.updated_at == clock.now
    assert count_rows(db_session) == 1


def test_get_base_returns_what_was_saved(db_session: Session, clock: FakeClock) -> None:
    service = make_service(db_session, clock)
    service.save_base("# Jordan Avery")

    assert service.get_base().content_markdown == "# Jordan Avery"


def test_the_text_is_stored_exactly_as_typed(db_session: Session, clock: FakeClock) -> None:
    text = "  # Jordan Avery\n\n- Built things  \n"

    resume = make_service(db_session, clock).save_base(text)

    assert resume.content_markdown == text
