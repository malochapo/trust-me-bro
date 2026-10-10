import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "src/dispatch/database/revisions/tenant/versions"
UI = ROOT / "src/dispatch/static/dispatch/src/signal"


def _instance(session, signal, project, entity=None):
    from tests.factories import SignalInstanceFactory

    instance = SignalInstanceFactory(
        project=project, signal=signal, entities=[entity] if entity else [], raw=json.dumps({"id": "x"})
    )
    session.add(instance)
    session.commit()
    return instance


def test_muted_signal_filters_new_instances_with_mute(session, signal, project):
    from dispatch.signal.models import SignalFilterAction
    from dispatch.signal.service import filter_signal

    signal.muted_until = datetime.now(timezone.utc) + timedelta(hours=2)
    session.commit()
    instance = _instance(session, signal, project)

    assert filter_signal(db_session=session, signal_instance=instance)
    assert instance.filter_action == SignalFilterAction.mute


def test_mute_ends_by_itself(session, signal, project):
    from dispatch.signal.models import SignalFilterAction
    from dispatch.signal.service import filter_signal

    signal.muted_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()
    instance = _instance(session, signal, project)

    filter_signal(db_session=session, signal_instance=instance)
    assert instance.filter_action != SignalFilterAction.mute


def test_mute_wins_over_an_active_snooze(session, entity, signal, project):
    from dispatch.signal.models import SignalFilterAction
    from dispatch.signal.service import filter_signal
    from tests.factories import SignalFilterFactory

    session.add(entity)
    snooze = SignalFilterFactory(
        name="snooze-under-mute",
        description="hidden test",
        expression=[{"or": [{"model": "Entity", "field": "id", "op": "==", "value": entity.id}]}],
        action="snooze",
        expiration=datetime.now(timezone.utc) + timedelta(days=1),
        project=project,
    )
    signal.filters = [snooze]
    signal.muted_until = datetime.now(timezone.utc) + timedelta(hours=1)
    session.commit()
    instance = _instance(session, signal, project, entity)

    assert filter_signal(db_session=session, signal_instance=instance)
    assert instance.filter_action == SignalFilterAction.mute


def test_api_models_carry_muted_until(session, signal):
    from dispatch.signal.models import SignalRead, SignalUpdate
    from dispatch.signal.service import update

    until = datetime(2031, 1, 2, 3, 4, tzinfo=timezone.utc)
    read = SignalRead.model_validate(signal)
    signal_in = SignalUpdate(**{**read.model_dump(), "muted_until": until})
    updated = update(db_session=session, signal=signal, signal_in=signal_in)
    session.commit()
    assert updated.muted_until.replace(tzinfo=timezone.utc) == until
    assert SignalRead.model_validate(updated).muted_until is not None


def test_a_tenant_migration_adds_the_column():
    found = [
        p.name
        for p in VERSIONS.glob("*.py")
        if re.search(r"add_column\(\s*[\"']signal[\"']", p.read_text())
        and re.search(r"[\"']muted_until[\"']", p.read_text())
    ]
    assert found, "no tenant migration adds signal.muted_until"


def test_ui_table_and_dialog():
    table = (UI / "Table.vue").read_text()
    assert re.search(r"title:\s*[\"']Muted until[\"']\s*,\s*(value|key):\s*[\"']muted_until[\"']", table, re.I)
    dialog = (UI / "NewEditDialog.vue").read_text()
    # the dialog edits the field, directly or through a computed wrapper (e.g. for time zones)
    assert "muted_until" in dialog
    assert re.search(r"v-model=\"[^\"]*muted[^\"]*\"", dialog, re.I)
