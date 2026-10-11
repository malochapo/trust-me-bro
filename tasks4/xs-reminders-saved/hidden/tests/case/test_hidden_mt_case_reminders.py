"""Hidden tests: the weekly case reminders of src/dispatch/case/scheduled.py.

The jobs run unwrapped (no scheduler, no per-organization session) against the test
session, with the date and time the dispatch.case modules see frozen, and with the
reminder message replaced by a recorder.
"""

import datetime as _dt
import inspect
import logging
import sys
import types

import pytest

MONDAY = _dt.datetime(2025, 8, 18, 18, 0, 5)  # naive UTC, like the case timestamps
TUESDAY = _dt.datetime(2025, 8, 19, 18, 0, 5)


def _case_modules():
    import dispatch.case.scheduled  # noqa: F401  (registers the jobs)

    return [
        module
        for name, module in list(sys.modules.items())
        if module is not None and (name == "dispatch.case" or name.startswith("dispatch.case."))
    ]


def _job(name):
    from dispatch.scheduler import scheduler

    _case_modules()
    task = next(t for t in scheduler.registered_tasks if t["name"] == name)
    return inspect.unwrap(task["func"])


def _freeze(monkeypatch, now):
    """The dispatch.case modules see `now` (naive UTC) as the current time."""

    class FrozenDate(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date(now.year, now.month, now.day)

    class FrozenDatetime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return now
            return now.replace(tzinfo=_dt.timezone.utc).astimezone(tz)

        @classmethod
        def utcnow(cls):
            return now

        @classmethod
        def today(cls):
            return now

    frozen_module = types.ModuleType("datetime")
    frozen_module.__dict__.update(vars(_dt))
    frozen_module.date, frozen_module.datetime = FrozenDate, FrozenDatetime

    for module in _case_modules():
        for attr, value in list(vars(module).items()):
            if value is _dt.date:
                monkeypatch.setattr(module, attr, FrozenDate)
            elif value is _dt.datetime:
                monkeypatch.setattr(module, attr, FrozenDatetime)
            elif value is _dt:
                monkeypatch.setattr(module, attr, frozen_module)


@pytest.fixture
def sent(monkeypatch):
    """Ids of the cases a close reminder was sent for."""
    calls = []

    def record(case=None, db_session=None, *args, **kwargs):
        calls.append(case.id)

    for module in _case_modules():
        if hasattr(module, "send_case_close_reminder"):
            monkeypatch.setattr(module, "send_case_close_reminder", record)
    return calls


def _case(session, project, status, **fields):
    from tests.factories import CaseFactory

    case = CaseFactory(project=project)
    case.status = status
    for key, value in fields.items():
        setattr(case, key, value)
    session.add(case)
    session.commit()
    return case


def test_close_reminder_goes_out_on_mondays(session, project, monkeypatch, sent):
    from dispatch.case.enums import CaseStatus

    case = _case(
        session,
        project,
        CaseStatus.triage,
        created_at=MONDAY - _dt.timedelta(days=11),
        triage_at=MONDAY - _dt.timedelta(days=10),
    )
    _freeze(monkeypatch, MONDAY)

    _job("case-close-reminder")(db_session=session, project=project)
    assert sent == [case.id]


def test_stable_reminder_goes_out_on_mondays(session, project, monkeypatch, sent):
    from dispatch.case.enums import CaseStatus

    case = _case(
        session,
        project,
        CaseStatus.stable,
        created_at=MONDAY - _dt.timedelta(days=12),
        triage_at=MONDAY - _dt.timedelta(days=11),
        stable_at=MONDAY - _dt.timedelta(days=10),
    )
    _freeze(monkeypatch, MONDAY)

    _job("case-stable-reminder")(db_session=session, project=project)
    assert sent == [case.id]


def test_no_weekly_reminder_on_other_days(session, project, monkeypatch, sent):
    from dispatch.case.enums import CaseStatus

    _case(
        session,
        project,
        CaseStatus.triage,
        created_at=TUESDAY - _dt.timedelta(days=11),
        triage_at=TUESDAY - _dt.timedelta(days=10),
    )
    _case(
        session,
        project,
        CaseStatus.stable,
        created_at=TUESDAY - _dt.timedelta(days=12),
        triage_at=TUESDAY - _dt.timedelta(days=11),
        stable_at=TUESDAY - _dt.timedelta(days=10),
    )
    _freeze(monkeypatch, TUESDAY)

    _job("case-close-reminder")(db_session=session, project=project)
    _job("case-stable-reminder")(db_session=session, project=project)
    assert sent == []
