import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "src/dispatch/database/revisions/tenant/versions"
UI = ROOT / "src/dispatch/static/dispatch/src/signal"


def test_create_read_and_update_keep_the_reason(session, user, project):
    from dispatch.signal.models import SignalFilterCreate, SignalFilterRead, SignalFilterUpdate
    from dispatch.signal.service import create_signal_filter, get_signal_filter, update_signal_filter

    created = create_signal_filter(
        db_session=session,
        creator=user,
        signal_filter_in=SignalFilterCreate(
            name="with-reason",
            description="d",
            expression=[{}],
            project=project,
            reason="known scanner, ticket SEC-1234",
        ),
    )
    stored = get_signal_filter(db_session=session, signal_filter_id=created.id)
    assert stored.reason == "known scanner, ticket SEC-1234"
    assert SignalFilterRead.model_validate(stored).reason == "known scanner, ticket SEC-1234"

    updated = update_signal_filter(
        db_session=session,
        signal_filter=stored,
        signal_filter_in=SignalFilterUpdate(
            id=stored.id, name="with-reason", expression=[{}], reason="scanner retired"
        ),
    )
    assert updated.reason == "scanner retired"


def test_reason_is_optional(session, user, project):
    from dispatch.signal.models import SignalFilterCreate, SignalFilterRead
    from dispatch.signal.service import create_signal_filter

    created = create_signal_filter(
        db_session=session,
        creator=user,
        signal_filter_in=SignalFilterCreate(
            name="no-reason", description="d", expression=[{}], project=project
        ),
    )
    assert SignalFilterRead.model_validate(created).reason is None


def test_a_tenant_migration_adds_the_column():
    found = [
        path.name
        for path in VERSIONS.glob("*.py")
        if re.search(r"add_column\(\s*[\"']signal_filter[\"']", path.read_text())
        and re.search(r"[\"']reason[\"']", path.read_text())
    ]
    assert found, "no tenant migration adds signal_filter.reason"


def test_snoozes_table_has_a_reason_column():
    text = (UI / "instance/TableInstanceSnoozes.vue").read_text()
    assert re.search(r"title:\s*[\"']Reason[\"']\s*,\s*(value|key):\s*[\"']reason[\"']", text)


def test_create_dialog_lets_users_type_a_reason():
    text = (UI / "filter/SignalFilterCreateDialog.vue").read_text()
    assert re.search(r"v-model=\"[^\"]*\breason\b[^\"]*\"", text)
