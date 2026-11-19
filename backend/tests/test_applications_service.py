import pytest
from sqlalchemy.orm import Session

from app.repositories.applications import ApplicationRepository
from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.applications import ApplicationNotFound, ApplicationService


def make_service(session: Session) -> ApplicationService:
    return ApplicationService(ApplicationRepository(session), TimelineRepository(session))


def new_payload(**overrides) -> ApplicationCreate:
    data = {
        "company": "Northwind Freight",
        "role": "Senior Backend Engineer",
        "source": "linkedin",
        "posting_url": "https://northwind.example/careers/1",
        "posting_text": "Build services.",
    }
    return ApplicationCreate(**{**data, **overrides})


def test_new_application_starts_in_saved_stage(db_session: Session) -> None:
    application = make_service(db_session).create(new_payload()).application

    assert application.id is not None
    assert application.stage.value == "saved"
    assert application.created_at is not None


def test_update_changes_only_the_five_editable_fields(db_session: Session) -> None:
    service = make_service(db_session)
    created = service.create(new_payload()).application

    updated = service.update(
        created.id,
        ApplicationUpdate(
            company="Larkspur Health",
            role="Staff Engineer",
            source="referral",
            posting_url="https://larkspur.example/jobs/9",
            posting_text="New text.",
        ),
    ).application

    assert (updated.company, updated.role) == ("Larkspur Health", "Staff Engineer")
    assert updated.source.value == "referral"
    assert updated.posting_url == "https://larkspur.example/jobs/9"
    assert updated.posting_text == "New text."
    assert updated.stage.value == "saved"
    assert updated.created_at == created.created_at


def test_update_missing_id_raises_not_found(db_session: Session) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session).update(999, ApplicationUpdate(company="X"))


def test_get_missing_id_raises_not_found(db_session: Session) -> None:
    with pytest.raises(ApplicationNotFound):
        make_service(db_session).get(999)


def test_list_is_newest_first(db_session: Session) -> None:
    service = make_service(db_session)
    first = service.create(new_payload(company="First")).application
    second = service.create(new_payload(company="Second")).application

    assert [v.application.id for v in service.list().items] == [second.id, first.id]
