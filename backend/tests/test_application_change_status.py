import pytest

from app.db import SessionLocal
from app.models import Application
from app.services import applications as application_service
from app.services.applications import change_status
from tests.email_helpers import make_application, make_email, read_events, read_status


def test_change_status_records_source_and_email_id():
    application_id = make_application()
    email_id = make_email()
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        changed = change_status(db, application, "interview", source="email", email_id=email_id)
        db.commit()
    assert changed is True
    assert read_status(application_id) == "interview"
    assert read_events(application_id) == [("applied", "interview", "email", email_id)]


def test_default_source_is_manual():
    application_id = make_application()
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        change_status(db, application, "under_review")
        db.commit()
    assert read_events(application_id) == [("applied", "under_review", "manual", None)]


def test_same_status_writes_nothing():
    application_id = make_application()
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        changed = change_status(db, application, "applied")
        db.commit()
    assert changed is False
    assert read_events(application_id) == []


def test_change_status_does_not_commit_by_itself():
    application_id = make_application()
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        change_status(db, application, "interview")
        db.rollback()
    assert read_status(application_id) == "applied"
    assert read_events(application_id) == []


def test_status_is_not_saved_when_the_event_fails(monkeypatch):
    application_id = make_application()

    def boom(*args, **kwargs):
        raise RuntimeError("event failed")

    monkeypatch.setattr(application_service, "ApplicationEvent", boom)
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        with pytest.raises(RuntimeError):
            change_status(db, application, "interview")
            db.commit()
        db.rollback()
    assert read_status(application_id) == "applied"
    assert read_events(application_id) == []