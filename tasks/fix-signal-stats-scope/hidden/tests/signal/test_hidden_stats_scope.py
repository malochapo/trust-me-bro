from datetime import datetime, timedelta, timezone


def _setup(session, project, expires_a, expires_b):
    """Two signals sharing one entity, each with one snooze filter on that entity."""
    from tests.factories import EntityFactory, EntityTypeFactory, SignalFactory, SignalFilterFactory

    entity_type = EntityTypeFactory(project=project)
    entity = EntityFactory(entity_type=entity_type, project=project)
    signal_a = SignalFactory(project=project, name="Signal A", external_id="hidden-a", variant="hidden-a")
    signal_b = SignalFactory(project=project, name="Signal B", external_id="hidden-b", variant="hidden-b")
    session.add_all([entity_type, entity, signal_a, signal_b])
    session.commit()

    for signal, expires in ((signal_a, expires_a), (signal_b, expires_b)):
        # build the filter first: the factory commits, which would drop a pending append
        snooze = SignalFilterFactory(
            name=f"snooze-{signal.name}",
            description="hidden test",
            expression=[
                {"or": [{"model": "Entity", "field": "id", "op": "==", "value": entity.id}]}
            ],
            action="snooze",
            expiration=datetime.now(timezone.utc) + expires,
            project=project,
        )
        signal.filters.append(snooze)
        session.commit()
    return entity, entity_type, signal_a, signal_b


def _stats(session, entity, entity_type, signal_id=None):
    from dispatch.signal.service import get_signal_stats

    return get_signal_stats(
        db_session=session,
        entity_value=entity.value,
        entity_type_id=entity_type.id,
        signal_id=signal_id,
    )


def test_per_signal_stats_count_only_that_signals_snoozes(session, project):
    entity, entity_type, signal_a, signal_b = _setup(
        session, project, timedelta(days=3), timedelta(days=3)
    )

    for signal in (signal_a, signal_b):
        stats = _stats(session, entity, entity_type, signal.id)
        assert stats.num_snoozes_active == 1
        assert stats.num_snoozes_expired == 0


def test_per_signal_stats_split_active_and_expired(session, project):
    entity, entity_type, signal_a, signal_b = _setup(
        session, project, timedelta(days=-3), timedelta(days=3)
    )

    stats_a = _stats(session, entity, entity_type, signal_a.id)
    assert (stats_a.num_snoozes_active, stats_a.num_snoozes_expired) == (0, 1)

    stats_b = _stats(session, entity, entity_type, signal_b.id)
    assert (stats_b.num_snoozes_active, stats_b.num_snoozes_expired) == (1, 0)


def test_global_stats_still_count_every_signal(session, project):
    entity, entity_type, _, _ = _setup(session, project, timedelta(days=-3), timedelta(days=3))

    stats = _stats(session, entity, entity_type)
    assert (stats.num_snoozes_active, stats.num_snoozes_expired) == (1, 1)
