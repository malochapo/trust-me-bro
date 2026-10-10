"""Writes the plant patches from edits made on top of upstream Dispatch.

Run once by a maintainer, not by the benchmark: the patches it writes are
committed under fixture/plants/. Usage:
    python3 -I author_plants.py <dispatch checkout at the pinned commit> <out dir>
Each plant is diffed against the previous one, in the order they enter history.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])


def edit(path, old, new, count=1):
    p = REPO / path
    text = p.read_text()
    if text.count(old) != count:
        sys.exit(f"{path}: expected {count} match(es) for {old!r}, found {text.count(old)}")
    p.write_text(text.replace(old, new))


def write(path, text):
    p = REPO / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def snapshot(name):
    subprocess.run(["git", "-C", REPO, "add", "-A"], check=True)
    diff = subprocess.run(
        ["git", "-C", REPO, "diff", "--cached", "--binary"],
        check=True, capture_output=True, text=True,
    ).stdout
    (OUT / f"{name}.patch").write_text(diff)
    subprocess.run(
        ["git", "-C", REPO, "-c", "user.name=a", "-c", "user.email=a@a", "commit", "-qm", name],
        check=True,
    )


def t0_test_teardown():
    edit(
        "tests/conftest.py",
        """    Session.configure(bind=schema_engine)
    yield
    drop_database(str(config.SQLALCHEMY_DATABASE_URI))
""",
        """    Session.configure(bind=schema_engine)
    yield
    # release every pooled connection, or Postgres refuses to drop the database
    Session.remove()
    engine.dispose()
    drop_database(str(config.SQLALCHEMY_DATABASE_URI))
""",
    )


def p0_log_filter_outcome():
    f = "src/dispatch/signal/flows.py"
    edit(
        f,
        """    # we don't need to continue if a filter action took place
    if signal_service.filter_signal(
        db_session=db_session,
        signal_instance=signal_instance,
    ):
""",
        """    # we don't need to continue if a filter action took place
    if signal_service.filter_signal(
        db_session=db_session,
        signal_instance=signal_instance,
    ):
        log.info(
            "Signal instance %s (%s) filtered: action=%s case_id=%s",
            signal_instance.id,
            signal_instance.signal.name,
            signal_instance.filter_action,
            signal_instance.case_id,
        )
""",
    )
    edit(
        f,
        """    case = case_service.create(db_session=db_session, case_in=case_in, current_user=current_user)
    signal_instance.case = case

    db_session.commit()
""",
        """    case = case_service.create(db_session=db_session, case_in=case_in, current_user=current_user)
    signal_instance.case = case

    db_session.commit()
    log.info(
        "Signal instance %s (%s) created case %s",
        signal_instance.id,
        signal_instance.signal.name,
        case.id,
    )
""",
    )


def p1_default_dedup_window():
    edit(
        "src/dispatch/config.py",
        """DISPATCH_UI_URL = config("DISPATCH_UI_URL", default="http://localhost:8080")
""",
        """DISPATCH_UI_URL = config("DISPATCH_UI_URL", default="http://localhost:8080")

# signals
SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES = config(
    "SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES", cast=int, default=45
)
""",
    )
    f = "src/dispatch/signal/service.py"
    edit(
        f,
        "from dispatch.case.type.models import CaseType\n",
        "from dispatch.case.type.models import CaseType\nfrom dispatch.config import SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES\n",
    )
    edit(
        f,
        "        default_dedup_window = datetime.now(timezone.utc) - timedelta(hours=1)\n",
        "        default_dedup_window = datetime.now(timezone.utc) - timedelta(\n"
        "            minutes=SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES\n"
        "        )\n",
    )


REDACTION = '''"""Masks sensitive values in the raw payload of a signal instance."""

from collections.abc import Iterable

from dispatch.config import SIGNAL_REDACTED_RAW_FIELDS

MASK = "[REDACTED]"


def redact_raw(raw, fields: Iterable[str] = SIGNAL_REDACTED_RAW_FIELDS):
    """Returns a copy of raw where the value of every key named in fields is masked.

    Keys match case-insensitively, at any depth, inside dicts and lists.
    Anything that is not a dict or a list is returned unchanged.
    """
    names = {field.strip().lower() for field in fields if field.strip()}
    return _redact(raw, names)


def _redact(value, names):
    if isinstance(value, dict):
        return {
            key: MASK if str(key).lower() in names else _redact(item, names)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, names) for item in value]
    return value
'''


def p2_redact_raw():
    edit(
        "src/dispatch/config.py",
        """    "SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES", cast=int, default=45
)
""",
        """    "SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES", cast=int, default=45
)
SIGNAL_REDACTED_RAW_FIELDS = config(
    "SIGNAL_REDACTED_RAW_FIELDS",
    cast=CommaSeparatedStrings,
    default="password,secret,api_key,session_token,authorization",
)
""",
    )
    write("src/dispatch/signal/redaction.py", REDACTION)
    f = "src/dispatch/signal/flows.py"
    edit(
        f,
        "from dispatch.signal.models import SignalFilterAction, SignalInstance, SignalInstanceCreate\n",
        "from dispatch.signal.models import SignalFilterAction, SignalInstance, SignalInstanceCreate\n"
        "from dispatch.signal.redaction import redact_raw\n",
    )
    edit(
        f,
        """        log.error("signal_instance is None for id: %%s", signal_instance_id)
        return None
""",
        """        log.error("signal_instance is None for id: %%s", signal_instance_id)
        return None

    # mask sensitive values before entities are extracted from the payload
    signal_instance.raw = redact_raw(signal_instance.raw)

""",
    )


def p3_cases_page_size():
    f = "src/dispatch/static/dispatch/src/case/Table.vue"
    edit(f, "'items-per-page-options': [10, 25, 50, 100],", "'items-per-page-options': [10, 20, 40, 80],")
    edit(f, "const itemsPerPage = ref(25)\n", "const itemsPerPage = ref(40)\n")


def p6_entity_stats_window():
    edit(
        "src/dispatch/static/dispatch/src/signal/instance/store.js",
        """        const fetchSignalStats = async (entity) => {
          try {
            return await SignalApi.getStats(entity.entity_type.id, entity.value)
""",
        """        // the entity table shows recent activity only
        const STATS_DAYS = 30
        const fetchSignalStats = async (entity) => {
          try {
            return await SignalApi.getStats(entity.entity_type.id, entity.value, STATS_DAYS)
""",
    )


def p5_snooze_refactor():
    edit(
        "src/dispatch/signal/service.py",
        """    for f in signal_instance.signal.filters:
        if not f.mode:
            log.warning(f"Signal filter {f.name} has no mode")
            continue

        if f.mode != SignalFilterMode.active:
            continue

        if not f.action:
            log.warning(f"Signal filter {f.name} has no action")
            continue

        if f.action != SignalFilterAction.snooze:
            continue

        if not f.expiration:
            log.warning(f"Signal filter {f.name} has no expiration date")
            continue

        if f.expiration.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            continue
""",
        """    for f in signal_instance.signal.filters:
        if f.mode != SignalFilterMode.active or f.action != SignalFilterAction.snooze:
            continue

        if not f.expiration:
            log.warning(f"Signal filter {f.name} has no expiration date")
            continue

        if f.expiration.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            break
""",
    )


def p4_dedup_window_seconds():
    f = "src/dispatch/signal/service.py"
    edit(
        f,
        """def filter_dedup(*, db_session: Session, signal_instance: SignalInstance) -> SignalInstance:
""",
        """def _window_start(seconds: int) -> datetime:
    \"\"\"Returns the start of a lookback window that ends now.\"\"\"
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


def filter_dedup(*, db_session: Session, signal_instance: SignalInstance) -> SignalInstance:
""",
    )
    edit(
        f,
        "        default_dedup_window = datetime.now(timezone.utc) - timedelta(\n"
        "            minutes=SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES\n"
        "        )\n",
        "        default_dedup_window = _window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)\n",
    )
    edit(
        f,
        "        window = datetime.now(timezone.utc) - timedelta(minutes=f.window)\n",
        "        # SignalFilter.window is stored in seconds\n"
        "        window = _window_start(f.window)\n",
    )


PLANTS = [
    ("t0-test-teardown", t0_test_teardown),
    ("p0-log-filter-outcome", p0_log_filter_outcome),
    ("p1-default-dedup-window", p1_default_dedup_window),
    ("p2-redact-raw", p2_redact_raw),
    ("p3-cases-page-size", p3_cases_page_size),
    ("p6-entity-stats-window", p6_entity_stats_window),
    ("p5-snooze-refactor", p5_snooze_refactor),
    ("p4-dedup-window-seconds", p4_dedup_window_seconds),
]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, plant in PLANTS:
        plant()
        snapshot(name)
        print("wrote", name)
