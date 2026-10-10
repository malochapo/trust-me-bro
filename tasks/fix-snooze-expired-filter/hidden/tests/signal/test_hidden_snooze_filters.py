import json
from datetime import datetime, timedelta, timezone

import pytest


def _snooze_filter(entity, project, name, expires_in):
    from tests.factories import SignalFilterFactory

    return SignalFilterFactory(
        name=name,
        description="hidden test",
        expression=[{"or": [{"model": "Entity", "field": "id", "op": "==", "value": entity.id}]}],
        action="snooze",
        expiration=datetime.now(timezone.utc) + expires_in,
        project=project,
    )


@pytest.mark.parametrize("expired_first", [True, False])
def test_active_snooze_applies_next_to_an_expired_one(session, entity, signal, project, expired_first):
    from dispatch.signal.models import SignalFilterAction
    from dispatch.signal.service import filter_signal
    from tests.factories import SignalInstanceFactory

    session.add(entity)
    instance = SignalInstanceFactory(
        project=project, signal=signal, entities=[entity], raw=json.dumps({"id": "foo"})
    )
    session.add(instance)
    session.commit()

    expired = _snooze_filter(entity, project, f"expired-{expired_first}", timedelta(days=-7))
    active = _snooze_filter(entity, project, f"active-{expired_first}", timedelta(days=30))
    signal.filters = [expired, active] if expired_first else [active, expired]
    session.commit()

    assert filter_signal(db_session=session, signal_instance=instance)
    assert instance.filter_action == SignalFilterAction.snooze


def test_only_expired_snoozes_do_not_snooze(session, entity, signal, project):
    from dispatch.signal.service import filter_signal
    from tests.factories import SignalInstanceFactory

    session.add(entity)
    instance = SignalInstanceFactory(
        project=project, signal=signal, entities=[entity], raw=json.dumps({"id": "foo"})
    )
    session.add(instance)
    session.commit()

    signal.filters = [
        _snooze_filter(entity, project, "expired-a", timedelta(days=-7)),
        _snooze_filter(entity, project, "expired-b", timedelta(days=-1)),
    ]
    session.commit()

    assert not filter_signal(db_session=session, signal_instance=instance)
