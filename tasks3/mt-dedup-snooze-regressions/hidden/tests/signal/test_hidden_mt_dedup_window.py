"""Hidden tests: a deduplication filter's window is in minutes, as the UI shows it."""

import json
from datetime import datetime, timedelta, timezone


def _two_instances(session, signal, project, window, minutes_apart):
    """An instance from `minutes_apart` minutes ago, a new one for the same entity, and a
    deduplication filter on that entity's type with the given window."""
    from tests.factories import (
        EntityFactory,
        EntityTypeFactory,
        SignalFilterFactory,
        SignalInstanceFactory,
    )

    entity_type = EntityTypeFactory(project=project)
    session.add(entity_type)
    signal.entity_types.append(entity_type)

    entity = EntityFactory(entity_type=entity_type, project=project)
    session.add(entity)

    earlier = SignalInstanceFactory(
        project=project,
        signal=signal,
        entities=[entity],
        raw=json.dumps({"id": "foo"}),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_apart),
    )
    session.add(earlier)
    latest = SignalInstanceFactory(
        project=project,
        signal=signal,
        entities=[entity],
        raw=json.dumps({"id": "foo"}),
    )
    session.add(latest)
    session.commit()

    # Build the filter before touching signal.filters: the factory commits, and an
    # append evaluated against the collection loaded before that commit is lost.
    dedup_filter = SignalFilterFactory(
        name=f"mt-dedup-{window}-{minutes_apart}",
        description="hidden test",
        expression=[
            {"or": [{"model": "EntityType", "field": "id", "op": "==", "value": entity_type.id}]}
        ],
        action="deduplicate",
        window=window,
        project=project,
    )
    signal.filters.append(dedup_filter)
    session.commit()
    assert [f.id for f in signal.filters] == [dedup_filter.id]
    return earlier, latest


def test_window_of_30_groups_instances_10_minutes_apart(session, signal, project):
    from dispatch.signal.models import SignalFilterAction
    from dispatch.signal.service import filter_signal

    earlier, latest = _two_instances(session, signal, project, window=30, minutes_apart=10)

    assert filter_signal(db_session=session, signal_instance=latest)
    assert latest.filter_action == SignalFilterAction.deduplicate
    assert latest.case_id == earlier.case_id


def test_window_of_5_does_not_group_instances_10_minutes_apart(session, signal, project):
    from dispatch.signal.models import SignalFilterAction
    from dispatch.signal.service import filter_signal

    _, latest = _two_instances(session, signal, project, window=5, minutes_apart=10)

    assert not filter_signal(db_session=session, signal_instance=latest)
    assert latest.filter_action == SignalFilterAction.none
