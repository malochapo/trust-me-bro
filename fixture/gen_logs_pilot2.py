"""Generates the scheduler and API logs for the log-reminders-stopped task.

Twenty-four days of `dispatch scheduler start` and `dispatch server start` output, as a log
platform exports it: one line per record, prefixed with a UTC timestamp and the pod name. Both
deployments roll twice; the second rollout ships the commit that compares isoweekday() with
calendar.MONDAY (plant q4), so from then on the weekly case close and stable reminders are never
sent, while the jobs themselves keep running and every other reminder keeps going out. The noise
is drawn from messages the deployed code really logs, with line numbers taken from the commit each
pod runs. Seeded, so the files are identical on every build.

The scheduler runs with LOG_LEVEL=DEBUG and the API with LOG_LEVEL=WARN. Third-party debug output
(schedule, slack_sdk) is left out, and the 30-second sync jobs run elsewhere (the scheduler is
started with --exclude for each), which keeps the files at a readable size.

Usage: python3 -I fixture/gen_logs_pilot2.py <build dir>
Reads <build>/fixture.git and <build>/plants.json,
writes <build>/data/log-reminders-stopped/{scheduler,api}.log
"""

import json
import math
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

UTC = timezone.utc
START = datetime(2025, 7, 28, tzinfo=UTC)
END = datetime(2025, 8, 21, tzinfo=UTC)
# the pods running at START were rolled out two weeks earlier, before the window
EARLIER_DEPLOY = datetime(2025, 7, 16, 16, 52, 31, tzinfo=UTC)
DEPLOYS = [datetime(2025, 7, 30, 17, 10, 3, tzinfo=UTC), datetime(2025, 8, 13, 16, 40, 6, tzinfo=UTC)]
PLANT = "q4-reminder-day"
DB_OUTAGE = (datetime(2025, 8, 15, 14, 37, 52, tzinfo=UTC), datetime(2025, 8, 15, 14, 44, 31, tzinfo=UTC))
SLOW_COST_RUN = datetime(2025, 8, 16, 5, 0, tzinfo=UTC)  # the hourly case cost run after this takes ~5 min
# incident-sync-members hits Slack's rate limit on these runs
RATE_LIMITED = [(datetime(2025, 7, 31, 2, 30, tzinfo=UTC), datetime(2025, 7, 31, 4, 30, tzinfo=UTC)),
                (datetime(2025, 8, 16, 20, 30, tzinfo=UTC), datetime(2025, 8, 16, 21, 30, tzinfo=UTC))]

SITE = "/usr/local/lib/python3.11/site-packages"
STDLIB = "/usr/local/lib/python3.11"
IMAGE = "registry.example.com/dispatch:main-{}"
POD_CHARS = "bcdfghjklmnpqrstvwxz2456789"
ORG = "default"
PROJECTS = [("default", 1), ("security", 2)]
SEC_TEAM = ["a.chen", "m.okafor", "s.lindqvist", "r.patel", "d.moreau", "k.tanaka"]
ENG_TEAM = ["l.nguyen", "p.walsh", "t.becker"]
STARLETTE_WARNING = [
    f"{SITE}/starlette/config.py:60: UserWarning: Config file '.env' not found.",
    "  warnings.warn(f\"Config file '{env_file}' not found.\")",
]
SIGNAL_TITLES = [
    "GuardDuty: Unauthorized API call", "Okta: Impossible travel", "CrowdStrike: Malware detected",
    "Okta: MFA reset from new device", "GitHub: Personal access token exposed", "AWS: Root account login",
    "CrowdStrike: Suspicious PowerShell", "Google Workspace: External file share spike",
    "Okta: Suspicious OAuth consent grant", "AWS: S3 bucket policy made public", "Lambda: Function URL exposed",
]
ENG_TITLES = ["Vendor access review", "Lost laptop report",
              "Phishing report from finance", "Contractor offboarding check"]

# --- third-party frames (versions pinned or resolved at image build time) ------------------------
SLACK_SDK_LINES = {  # client.conversations_members, api_call, _sync_send, _urllib_api_call, validate
    "3.34.0": (3166, 159, 190, 321, 199),
    "3.36.0": (3220, 169, 200, 331, 197),
}
SLACK_URL = "https://slack.com/api/{}"
PG = '"dispatch-db.internal" (10.20.4.17), port 5432'
PG_ERRORS = {
    "closed": "server closed the connection unexpectedly\n\tThis probably means the server terminated abnormally\n\tbefore or while processing the request.\n",
    "refused": f"connection to server at {PG} failed: Connection refused\n\tIs the server running on that host and accepting TCP/IP connections?\n",
    "starting": f"connection to server at {PG} failed: FATAL:  the database system is starting up\n",
}
ORG_SQL = (
    "[SQL: SELECT dispatch_core.organization.id AS dispatch_core_organization_id, dispatch_core.organization.name AS dispatch_core_organization_name, "
    "dispatch_core.organization.slug AS dispatch_core_organization_slug, dispatch_core.organization.\"default\" AS dispatch_core_organization_default, "
    "dispatch_core.organization.description AS dispatch_core_organization_description, dispatch_core.organization.banner_enabled AS dispatch_core_organization_banner_enabled, "
    "dispatch_core.organization.banner_color AS dispatch_core_organization_banner_color, dispatch_core.organization.banner_text AS dispatch_core_organization_banner_text, "
    "dispatch_core.organization.search_vector AS dispatch_core_organization_search_vector \nFROM dispatch_core.organization]"
)
SQLA_BACKGROUND = "(Background on this error at: https://sqlalche.me/e/20/e3q8)"
# SQLAlchemy 2.0.8 / psycopg2 frames, captured from the fixture code against a stopped PostgreSQL
SQLA_ORM_ITER = """\
  File "{SITE}/sqlalchemy/orm/query.py", line 2841, in __iter__
    result = self._iter()
             ^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/orm/query.py", line 2855, in _iter
    result: Union[ScalarResult[_T], Result[_T]] = self.session.execute(
                                                  ^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/orm/session.py", line 2229, in execute
    return self._execute_internal(
           ^^^^^^^^^^^^^^^^^^^^^^^"""
SQLA_EXECUTE = """\
  File "{SITE}/sqlalchemy/engine/base.py", line 1964, in _exec_single_context
    self.dialect.do_execute(
  File "{SITE}/sqlalchemy/engine/default.py", line 748, in do_execute
    cursor.execute(statement, parameters)"""
SQLA_ORM_EXECUTE = """\
  File "{SITE}/sqlalchemy/orm/session.py", line 2124, in _execute_internal
    result: Result[Any] = compile_state_cls.orm_execute_statement(
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/orm/context.py", line 253, in orm_execute_statement
    result = conn.execute(
             ^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/base.py", line 1414, in execute
    return meth(
           ^^^^^
  File "{SITE}/sqlalchemy/sql/elements.py", line 486, in _execute_on_connection
    return connection._execute_clauseelement(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/base.py", line 1638, in _execute_clauseelement
    ret = self._execute_context(
          ^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/base.py", line 1842, in _execute_context
    return self._exec_single_context(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/base.py", line 1983, in _exec_single_context
    self._handle_dbapi_exception(
  File "{SITE}/sqlalchemy/engine/base.py", line 2326, in _handle_dbapi_exception
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e"""
SQLA_ORM_CONNECT = """\
  File "{SITE}/sqlalchemy/orm/session.py", line 2114, in _execute_internal
    conn = self._connection_for_bind(bind)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/orm/session.py", line 1981, in _connection_for_bind
    return trans._connection_for_bind(engine, execution_options)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<string>", line 2, in _connection_for_bind
  File "{SITE}/sqlalchemy/orm/state_changes.py", line 137, in _go
    ret_value = fn(self, *arg, **kw)
                ^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/orm/session.py", line 1108, in _connection_for_bind
    conn = bind.connect()
           ^^^^^^^^^^^^^^"""
SQLA_CONNECT_WRAP = """\
  File "{SITE}/sqlalchemy/engine/base.py", line 3251, in connect
    return self._connection_cls(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/base.py", line 147, in __init__
    Connection._handle_dbapi_exception_noconnection(
  File "{SITE}/sqlalchemy/engine/base.py", line 2413, in _handle_dbapi_exception_noconnection
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e"""
SQLA_CONNECT_HEAD = """\
  File "{SITE}/sqlalchemy/engine/base.py", line 145, in __init__
    self._dbapi_connection = engine.raw_connection()
                             ^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/base.py", line 3275, in raw_connection
    return self.pool.connect()
           ^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/pool/base.py", line 455, in connect
    return _ConnectionFairy._checkout(self)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/pool/base.py", line 1271, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"""
SQLA_POOL_REUSE = """\
  File "{SITE}/sqlalchemy/pool/base.py", line 724, in checkout
    with util.safe_reraise():
  File "{SITE}/sqlalchemy/util/langhelpers.py", line 147, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "{SITE}/sqlalchemy/pool/base.py", line 722, in checkout
    dbapi_connection = rec.get_connection()
                       ^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/pool/base.py", line 842, in get_connection
    self.__connect()"""
SQLA_POOL_NEW = """\
  File "{SITE}/sqlalchemy/pool/base.py", line 719, in checkout
    rec = pool._do_get()
          ^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/pool/impl.py", line 168, in _do_get
    with util.safe_reraise():
  File "{SITE}/sqlalchemy/util/langhelpers.py", line 147, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "{SITE}/sqlalchemy/pool/impl.py", line 166, in _do_get
    return self._create_connection()
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/pool/base.py", line 396, in _create_connection
    return _ConnectionRecord(self)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/pool/base.py", line 681, in __init__
    self.__connect()"""
SQLA_CONNECT_TAIL = """\
  File "{SITE}/sqlalchemy/pool/base.py", line 905, in __connect
    with util.safe_reraise():
  File "{SITE}/sqlalchemy/util/langhelpers.py", line 147, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "{SITE}/sqlalchemy/pool/base.py", line 901, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/create.py", line 636, in connect
    return dialect.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/default.py", line 580, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"""
STARLETTE_CALL_NEXT = """\
  File "{SITE}/starlette/middleware/base.py", line 156, in call_next
    raise app_exc
  File "{SITE}/starlette/middleware/base.py", line 141, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)"""
STARLETTE_DISPATCH = """\
  File "{SITE}/starlette/middleware/base.py", line 176, in __call__
    with recv_stream, send_stream, collapse_excgroups():
  File "{STDLIB}/contextlib.py", line 158, in __exit__
    self.gen.throw(typ, value, traceback)
  File "{SITE}/starlette/_utils.py", line 82, in collapse_excgroups
    raise exc
  File "{SITE}/starlette/middleware/base.py", line 178, in __call__
    response = await self.dispatch_func(request, call_next)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"""
SENTRY_ASGI = """\
  File "{SITE}/sentry_asgi/middleware.py", line 22, in __call__
    raise exc from None
  File "{SITE}/sentry_asgi/middleware.py", line 19, in __call__
    await self.app(scope, receive, send)"""
SQLA_INSPECT = """\
  File "{SITE}/sqlalchemy/inspection.py", line 111, in inspect
    ret = reg(subject)
          ^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/reflection.py", line 304, in _engine_insp
    return Inspector._construct(Inspector._init_engine, bind)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "{SITE}/sqlalchemy/engine/reflection.py", line 237, in _construct
    init(self, bind)
  File "{SITE}/sqlalchemy/engine/reflection.py", line 248, in _init_engine
    engine.connect().close()
    ^^^^^^^^^^^^^^^^"""


def lib(block):
    return block.replace("{SITE}", SITE).replace("{STDLIB}", STDLIB).split("\n")


def fmt_ts(at):
    return f"{at.strftime('%Y-%m-%dT%H:%M:%S.')}{at.microsecond // 1000:03d}"


def git(fixture, *args):
    return subprocess.run(["git", "-C", str(fixture), *args], check=True, capture_output=True, text=True).stdout


def deployed_commit(fixture, when):
    """The newest commit on main at deploy time."""
    return git(fixture, "log", "-1", "--format=%H", f"--before={when.isoformat()}", "main").strip()


def render_frame(file, lineno, func, line, hl=None, eol=False, binop=None):
    """A Python 3.11 traceback entry, carets included."""
    stripped = line.strip()
    out = [f'  File "{file}", line {lineno}, in {func}', f"    {stripped}"]
    if hl:
        indent = len(line) - len(line.lstrip())
        start = line.index(hl)
        end = len(line.rstrip()) if eol else start + len(hl)
        if binop:
            out.append("    " + " " * (start - indent) + "~" * binop[0] + "^" * binop[1] + "~" * (end - start - sum(binop)))
        elif end - start < len(stripped):
            out.append("    " + " " * (start - indent) + "^" * (end - start))
    return out


class Source:
    """The code one pod runs: line numbers for what it logs, and the behaviour it ships."""

    def __init__(self, fixture, sha, q4):
        self.fixture, self.sha = fixture, sha
        self.files, self.cache = {}, {}
        self.has_q4 = subprocess.run(["git", "-C", str(fixture), "merge-base", "--is-ancestor", q4, sha]).returncode == 0
        scheduled = "\n".join(self.lines("case/scheduled.py"))
        # case/scheduled.py decides the reminder day; calendar.MONDAY is 0, isoweekday() runs 1..7
        self.reminder_weekday = 0 if "== calendar.MONDAY" in scheduled else 1
        assert self.has_q4 == (self.reminder_weekday == 0)
        body = scheduled[scheduled.index("def case_stable_reminder"):]
        self.stable_guard = "if case.stable_at:" in body
        try:
            pins = git(fixture, "show", f"{sha}:requirements-base.txt")
            self.slack_sdk = re.search(r"^slack-sdk==(\S+)", pins, re.M).group(1)
        except subprocess.CalledProcessError:
            self.slack_sdk = "3.36.0"  # unpinned after the move to uv; what the image build resolved
        self.plugins = self.entry_points()

    def lines(self, path):
        if path not in self.files:
            self.files[path] = git(self.fixture, "show", f"{self.sha}:src/dispatch/{path}").split("\n")
        return self.files[path]

    def find(self, path, anchor, after=None):
        lines = self.lines(path)
        start = next(i for i, line in enumerate(lines) if after in line) if after else 0
        for i in range(start, len(lines)):
            if anchor in lines[i]:
                return i + 1
        raise KeyError(f"{anchor!r} not in {path} at {self.sha[:8]}")

    def call_line(self, path, anchor, after=None):
        """The line a logging call reports: Python 3.11 gives the first line of the call."""
        key = (path, anchor, after)
        if key not in self.cache:
            n = self.find(path, anchor, after)
            lines = self.lines(path)
            i = n - 1
            while not re.search(r"\b(log|logger)\.(debug|info|warning|warn|error|exception)\(", lines[i]):
                i -= 1
                assert n - i < 6, key
            self.cache[key] = i + 1
        return self.cache[key]

    def rec(self, level, msg, path, func, anchor, after=None):
        return f"{level}:{msg}:{SITE}/dispatch/{path}:{func}:{self.call_line(path, anchor, after)}"

    def frame(self, path, func, anchor, after=None, **kw):
        n = self.find(path, anchor, after)
        return render_frame(f"{SITE}/dispatch/{path}", n, func, self.lines(path)[n - 1], **kw)

    def entry_points(self):
        try:
            text = git(self.fixture, "show", f"{self.sha}:pyproject.toml")
            names = re.findall(r'^([a-z0-9_]+) = "dispatch\.plugins\.', text, re.M)
        except subprocess.CalledProcessError:
            names = []
        if not names:
            text = git(self.fixture, "show", f"{self.sha}:setup.py")
            names = re.findall(r'^\s*"([a-z0-9_]+) = dispatch\.plugins\.', text, re.M)
        assert names
        return names


class Log:
    def __init__(self):
        self.lines = []

    def emit(self, at, pod, text):
        if not START <= at < END:
            return
        for part in text.split("\n"):
            self.lines.append((at, len(self.lines), f"{fmt_ts(at)}Z {pod} {part}"))

    def write(self, path):
        self.lines.sort(key=lambda line: (line[0], line[1]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(text for _, _, text in self.lines) + "\n")


class Pod:
    def __init__(self, rng, deployment, template, started, stopped, sha, src):
        suffix = "".join(rng.choice(POD_CHARS) for _ in range(5))
        self.name = f"{deployment}-{template}-{suffix}"
        self.started, self.stopped, self.sha, self.src = started, stopped, sha, src
        self.uptime = rng.uniform(4e5, 3e6)  # perf_counter() of the node when the pod starts
        self.heap = rng.choice(["7f3b", "7f52", "7f8e", "7fa1", "7fc4", "7fe0"])


def elapsed(pod, at, seconds):
    """What `time.perf_counter() - start` prints for a span of `seconds` ending at `at`."""
    end = pod.uptime + (at - pod.started).total_seconds()
    return repr(end - (end - seconds))


# --- the world the jobs look at ---------------------------------------------------------------------

class Tracked:
    """Something with a status history; move() also stamps triage_at/stable_at, as the app does."""

    def __init__(self, created, status):
        self.created = created
        self.timeline = [(created, status)]
        self.triage_at = self.stable_at = None

    def move(self, at, status):
        self.timeline.append((at, status))
        if status == "Triage":
            self.triage_at = at
        if status == "Stable":
            self.stable_at = at

    def status(self, at):
        current = None
        for when, status in self.timeline:
            if when <= at:
                current = status
        return current


class Case(Tracked):
    def __init__(self, project, title, created, assignee):
        super().__init__(created, "New")
        self.id = None
        self.project, self.title, self.assignee = project, title, assignee

    @property
    def name(self):
        return f"dispatch-{ORG}-{self.project}-{self.id}"


class Incident(Tracked):
    def __init__(self, iid, title, commander, created, tactical_every, executive_every):
        super().__init__(created, "Active")
        self.id, self.title, self.commander = iid, title, commander
        self.every = {"tactical": tactical_every, "executive": executive_every}
        self.reports = {"tactical": [], "executive": []}
        self.delayed = []  # (requested at, due at, report type)


def email(user):
    return f"{user}@example.com"


def build_cases(rng):
    """Cases from mid-June on, so the window opens on a realistic backlog."""
    cases = []

    def add(project, title, created, assignee):
        case = Case(project, title, created, assignee)
        cases.append(case)
        return case

    # long-running ones that are due a close reminder every Monday of the window
    c = add("security", "Okta: Suspicious OAuth consent grant", datetime(2025, 7, 8, 13, 55, 2, tzinfo=UTC), email("r.patel"))
    c.move(datetime(2025, 7, 8, 15, 12, tzinfo=UTC), "Triage")
    c.move(datetime(2025, 8, 20, 14, 3, tzinfo=UTC), "Closed")
    c = add("security", "AWS: Root account login", datetime(2025, 7, 10, 22, 31, 40, tzinfo=UTC), email("a.chen"))
    c.move(datetime(2025, 7, 11, 8, 2, tzinfo=UTC), "Triage")
    c.move(datetime(2025, 7, 11, 17, 26, tzinfo=UTC), "Stable")
    c = add("security", "Okta: MFA reset from new device", datetime(2025, 7, 15, 7, 12, 9, tzinfo=UTC), email("s.lindqvist"))
    c.move(datetime(2025, 7, 15, 10, 40, tzinfo=UTC), "Triage")
    c.move(datetime(2025, 8, 19, 16, 22, tzinfo=UTC), "Closed")
    for title, user, created, triaged, stable, closed in (
        ("CrowdStrike: Malware detected", "m.okafor", (7, 17, 21, 40), (7, 18, 9, 5), None, (8, 13, 11, 52)),
        ("AWS: S3 bucket policy made public", "d.moreau", (7, 24, 3, 12), (7, 24, 14, 30), None, (8, 6, 16, 8)),
        ("GuardDuty: Unauthorized API call", "k.tanaka", (7, 25, 19, 2), (7, 26, 8, 44), (7, 29, 10, 17), None),
        ("Okta: Impossible travel", "a.chen", (8, 6, 22, 48), (8, 7, 9, 31), None, None),
    ):
        c = add("security", title, datetime(2025, *created, tzinfo=UTC), email(user))
        c.move(datetime(2025, *triaged, tzinfo=UTC), "Triage")
        if stable:
            c.move(datetime(2025, *stable, tzinfo=UTC), "Stable")
        if closed:
            c.move(datetime(2025, *closed, tzinfo=UTC), "Closed")
    # moved to Stable through a path that never set stable_at
    c = add("security", "GitHub: Personal access token exposed", datetime(2025, 6, 18, 11, 9, 51, tzinfo=UTC), email("k.tanaka"))
    c.move(datetime(2025, 6, 18, 14, 0, tzinfo=UTC), "Triage")
    c.timeline.append((datetime(2025, 6, 23, 10, 15, tzinfo=UTC), "Stable"))
    # imported from the old tracker straight into Triage, so triage_at was never set
    c = add("security", "CrowdStrike: Suspicious PowerShell", datetime(2025, 6, 12, 8, 47, 3, tzinfo=UTC), email("d.moreau"))
    c.timeline.append((datetime(2025, 6, 12, 8, 47, 3, tzinfo=UTC), "Triage"))
    # assigned to someone who has left: the triage reminder keeps going to a Slack user that no longer exists
    c = add("security", "Google Workspace: External file share spike", datetime(2025, 8, 1, 10, 5, 37, tzinfo=UTC), email("j.ramirez"))
    c.move(datetime(2025, 8, 15, 16, 20, tzinfo=UTC), "Triage")
    c.move(datetime(2025, 8, 19, 11, 2, tzinfo=UTC), "Closed")
    # a detector misfire opens a pile of cases nobody is assigned to; they are bulk-closed on Monday
    burst = []
    at = datetime(2025, 8, 7, 14, 21, 7, tzinfo=UTC)
    for i in range(11):
        c = add("security", "Security Event Triage", at, None)
        c.move(datetime(2025, 8, 11, 15, 31, 12, tzinfo=UTC) + timedelta(milliseconds=60 * i + rng.randint(0, 90)), "Closed")
        burst.append(c)
        at += timedelta(seconds=rng.randint(40, 420))

    # the everyday flow: signal cases in security, a trickle in default
    t = datetime(2025, 6, 20, tzinfo=UTC)
    while t < END:
        t += timedelta(days=rng.expovariate(0.85))
        c = add("security", rng.choice(SIGNAL_TITLES), t, email(rng.choice(SEC_TEAM)) if rng.random() > 0.03 else None)
        if rng.random() < 0.5:  # false positive, closed straight from New
            c.move(t + timedelta(hours=rng.uniform(0.4, 20)), "Closed")
            continue
        triage = t + timedelta(days=rng.uniform(0.1, 1.9))
        c.move(triage, "Triage")
        r = rng.random()
        done = triage + timedelta(days=rng.uniform(0.3, 3.5) if r < 0.8 else rng.uniform(7, 12) if r < 0.96 else rng.uniform(12, 19))
        if rng.random() < 0.15:
            c.move(done, "Stable")
            done += timedelta(days=rng.uniform(4, 12))
        c.move(done, "Closed")
    # requests to the engineering side wait days before anyone triages them
    t = datetime(2025, 6, 24, 15, tzinfo=UTC)
    while t < END:
        c = add("default", rng.choice(ENG_TITLES), t, email(rng.choice(ENG_TEAM)))
        triage = t + timedelta(days=rng.uniform(2.2, 4.8))
        c.move(triage, "Triage")
        c.move(triage + timedelta(days=rng.uniform(0.2, 2.5)), "Closed")
        t += timedelta(days=rng.uniform(3.2, 4.6), hours=rng.uniform(-3, 3))

    # someone always sits on a new case for more than a day, so triage reminders go out every evening
    day = START
    while day < END:
        run = day + timedelta(hours=18)
        if not any(c.assignee and c.status(run) == "New" and (run - c.created).days >= 1 for c in cases):
            t = run - timedelta(days=1, hours=rng.uniform(1, 9))
            c = add("security", rng.choice(SIGNAL_TITLES), t, email(rng.choice(SEC_TEAM)))
            triage = run + timedelta(hours=rng.uniform(2, 30))
            c.move(triage, "Triage")
            c.move(triage + timedelta(days=rng.uniform(0.3, 3)), "Closed")
        day += timedelta(days=1)

    cases.sort(key=lambda case: case.created)
    next_id = 4702
    for case in cases:
        case.id = next_id
        next_id += rng.randint(1, 3)
    return cases, burst


def build_incidents():
    inc31 = Incident(31, "Elevated 5xx on api-gateway", email("l.nguyen"), datetime(2025, 7, 7, 14, 2, tzinfo=UTC), 24, 24)
    inc31.move(datetime(2025, 7, 9, 10, 31, tzinfo=UTC), "Stable")  # nobody closes it
    inc34 = Incident(34, "Okta session tokens replayed from unknown ASN", email("p.walsh"), datetime(2025, 8, 5, 9, 12, 44, tzinfo=UTC), 6, 12)
    inc34.reports["tactical"] += [datetime(2025, 8, 5, 10, 31, tzinfo=UTC), datetime(2025, 8, 5, 23, 48, tzinfo=UTC)]
    inc34.reports["executive"] += [datetime(2025, 8, 6, 8, 5, tzinfo=UTC)]
    inc34.delayed.append((datetime(2025, 8, 5, 20, 55, tzinfo=UTC), datetime(2025, 8, 5, 22, 55, tzinfo=UTC), "executive"))
    inc34.move(datetime(2025, 8, 6, 15, 40, tzinfo=UTC), "Stable")
    inc34.move(datetime(2025, 8, 8, 11, 5, tzinfo=UTC), "Closed")
    inc37 = Incident(37, "Build runners pulling unsigned images", email("t.becker"), datetime(2025, 8, 19, 13, 30, 5, tzinfo=UTC), 24, 24)
    inc37.move(datetime(2025, 8, 20, 10, 0, tzinfo=UTC), "Stable")
    return [inc31, inc34, inc37]


# --- the scheduler ------------------------------------------------------------------------------------

# every job `dispatch scheduler start` registers, in import order, less the three 30-second sync jobs
# (sync-active-stable-monitors, sync-active-stable-incident-tasks, sync-workflows) the pod excludes
JOBS = [
    ("case-close-reminder", "case/scheduled.py", "case_close_reminder", ("at", 18)),
    ("case-triage-reminder", "case/scheduled.py", "case_triage_reminder", ("at", 18)),
    ("case-stable-reminder", "case/scheduled.py", "case_stable_reminder", ("at", 18)),
    ("calculate-cases-response-cost", "case_cost/scheduled.py", "calculate_cases_response_cost", ("every", 3600)),
    ("sync-sources", "data/source/scheduled.py", "sync_sources", ("every", 3600)),
    ("sync-document-terms", "document/scheduled.py", "sync_document_terms", ("every", 86400)),
    ("create-evergreen-reminders", "evergreen/scheduled.py", "create_evergreen_reminders", ("monday", 18)),
    ("feedback-report-daily", "feedback/incident/scheduled.py", "feedback_report_daily", ("at", 18)),
    ("oncall-shift-feedback-ucan", "feedback/service/scheduled.py", "oncall_shift_feedback_ucan", ("at", 16)),
    ("oncall-shift-feedback-emea", "feedback/service/scheduled.py", "oncall_shift_feedback_emea", ("at", 6)),
    ("incident-auto-tagger", "incident/scheduled.py", "incident_auto_tagger", ("every", 3600)),
    ("incident-report-daily", "incident/scheduled.py", "incident_report_daily", ("at", 18)),
    ("incident-close-reminder", "incident/scheduled.py", "incident_close_reminder", ("at", 18)),
    ("incident-report-weekly", "incident/scheduled.py", "incident_report_weekly", ("monday", 18)),
    ("incident-sync-members", "incident/scheduled.py", "incident_sync_members", ("every", 3600)),
    ("calculate-incidents-response-cost", "incident_cost/scheduled.py", "calculate_incidents_response_cost", ("every", 3600)),
    ("incident-report-reminders", "report/scheduled.py", "incident_report_reminders", ("every", 3600)),
    ("incident-report-delayed-reminders", "report/scheduled.py", "incident_report_delayed_reminders", ("every", 300)),
    ("sync-tags", "tag/scheduled.py", "sync_tags", ("every", 3600)),
    ("build-tag-models", "tag/scheduled.py", "build_tag_models", ("every", 86400)),
    ("create-incident-tasks-reminders", "task/scheduled.py", "create_incident_tasks_reminders", ("every", 3600)),
    ("sync-incident-tasks-daily", "task/scheduled.py", "sync_incident_tasks_daily", ("every", 86400)),
    ("sync-terms", "term/scheduled.py", "sync_terms", ("every", 3600)),
]
UNTIMED = {"create-incident-tasks-reminders"}  # registered without @timer


def first_run(spec, reg):
    kind, value = spec
    if kind == "every":
        return reg + timedelta(seconds=value)
    day = reg.replace(hour=value, minute=0, second=0, microsecond=0)
    while day <= reg or (kind == "monday" and day.isoweekday() != 1):
        day += timedelta(days=1)
    return day


def next_run(spec, ran, rng):
    kind, value = spec
    if kind == "every":  # schedule counts the period from when the job was handed to the pool
        return ran + timedelta(seconds=value, microseconds=rng.randint(150, 400))
    return first_run(spec, ran)


def fullname(path, func):
    return "dispatch." + path[:-3].replace("/", ".") + "." + func


class Scheduler:
    """One scheduler pod: its startup, the jobs it runs and what they log."""

    def __init__(self, world, pod):
        self.w, self.pod, self.src, self.rng, self.log = world, pod, pod.src, world.rng, world.scheduler_log
        self.db_failures = 0

    def emit(self, at, text):
        self.log.emit(at, self.pod.name, text)

    def rec(self, at, level, msg, path, func, anchor, after=None):
        self.emit(at, self.src.rec(level, msg, path, func, anchor, after))

    def s(self, lo, hi):
        return timedelta(seconds=self.rng.uniform(lo, hi))

    def addr(self):
        return f"0x{self.pod.heap}{self.rng.getrandbits(28):07x}0"

    def timer(self, at, name, seconds):
        self.rec(at, "DEBUG", f"function.elapsed.time.{name}: {elapsed(self.pod, at, seconds)}",
                 "decorators.py", "wrapper", 'log.debug(f"function.elapsed.time.')

    def plugin(self, at, qualname, lo, hi):
        """A call into a plugin; plugin classes are decorated with @apply(timer)."""
        span = self.s(lo, hi)
        at += span
        self.timer(at, qualname, span.total_seconds())
        return at + self.s(0.0001, 0.0006)

    def slack(self, at, method, lo=0.25, hi=0.9):
        return self.plugin(at, f"dispatch.plugins.dispatch_slack.plugin.SlackConversationPlugin.{method}", lo, hi)

    def command_name(self, at):
        return self.slack(at, "get_command_name", 1.4e-06, 5.2e-06)

    # -- lifecycle

    def start(self):
        pod, at = self.pod, self.pod.started
        self.emit(at, f"[kubelet] Started container scheduler (image {IMAGE.format(pod.sha[:8])})")
        at += timedelta(milliseconds=2400 + self.rng.randint(0, 300))
        for line in STARLETTE_WARNING:
            self.emit(at, line)
        at += self.s(0.6, 0.9)
        for name in self.src.plugins:
            self.rec(at, "INFO", f"Attempting to load plugin: {name}", "common/utils/cli.py", "install_plugins", "Attempting to load plugin")
            at += self.s(0.002, 0.35 if name.startswith(("dispatch_slack", "google", "slack")) else 0.06)
            self.rec(at, "INFO", f"Successfully loaded plugin: {name}", "common/utils/cli.py", "install_plugins", "Successfully loaded plugin")
            at += self.s(0.0002, 0.001)
        self.emit(at, "Starting scheduler...")
        self.rec(at + self.s(0.0001, 0.0003), "INFO", "Starting scheduler...", "scheduler.py", "start", 'log.info("Starting scheduler...")')
        return at

    def stop(self):
        self.rec(self.pod.stopped, "DEBUG", "Stopping scheduler...", "scheduler.py", "stop", 'log.debug("Stopping scheduler...")')

    def run(self):
        loop = self.start()
        reg = self.pod.started + timedelta(seconds=3.1)
        period = 1.0 + self.rng.uniform(0.0002, 0.0009)  # run_pending() then sleep(1)
        queue = [[first_run(spec, reg), i, name, path, func, spec] for i, (name, path, func, spec) in enumerate(JOBS)]
        end = min(self.pod.stopped, END)
        while True:
            queue.sort(key=lambda job: (job[0], job[1]))
            offset = (queue[0][0] - loop).total_seconds()
            tick = loop + timedelta(seconds=math.ceil(offset / period) * period)
            if tick >= end:
                break
            for k, job in enumerate([job for job in queue if job[0] <= tick]):
                at = tick + timedelta(microseconds=170 * k + self.rng.randint(15, 90))
                if at >= START:
                    self.dispatch(job[2], job[3], job[4], at)
                job[0] = next_run(job[5], at, self.rng)
        if self.pod.stopped < END:
            self.stop()

    def dispatch(self, name, path, func, at):
        t0 = at
        if self.w.db_down(at):
            at = self.db_failure(fullname(path, func), at)
        else:
            at = getattr(self, func)(at + self.s(0.0005, 0.003))
        if name not in UNTIMED:
            self.timer(at, fullname(path, func), (at - t0).total_seconds() + 1e-5)

    # -- failure paths

    def db_failure(self, name, at):
        """The organization query in scheduled_project_task fails before any project is touched."""
        kind = self.w.db_error_kind(at, self.db_failures)
        self.db_failures += 1
        at += self.s(0.002, 0.009) if kind != "closed" else self.s(0.01, 0.04)
        src = self.src
        self.rec(at, "ERROR", f"Error trying to execute task: {name}", "decorators.py", "_execute_task_in_project_context",
                 'log.error(f"Error trying to execute task: {fullname(func)}")')
        psycopg = PG_ERRORS[kind]
        if kind == "closed":
            message = f"(psycopg2.OperationalError) {psycopg}\n{ORG_SQL}\n{SQLA_BACKGROUND}"
            cause = lib(SQLA_EXECUTE)
            chain = lib(SQLA_ORM_ITER) + lib(SQLA_ORM_EXECUTE) + lib(SQLA_EXECUTE)
        else:
            message = f"(psycopg2.OperationalError) {psycopg}\n{SQLA_BACKGROUND}"
            # the pool's records were invalidated by the first failure, so checkout reconnects them
            cause = lib(SQLA_CONNECT_HEAD) + lib(SQLA_POOL_REUSE) + lib(SQLA_CONNECT_TAIL)
            chain = lib(SQLA_ORM_ITER) + lib(SQLA_ORM_CONNECT) + lib(SQLA_CONNECT_WRAP) + cause
        record = src.rec("ERROR", message, "decorators.py", "_execute_task_in_project_context", "log.exception(e)",
                         after='log.error(f"Error trying to execute task: {fullname(func)}")')
        loop_frame = src.frame("decorators.py", "_execute_task_in_project_context", "for organization in organization_service.get_all(")
        text = [record, "Traceback (most recent call last):", *cause, f"psycopg2.OperationalError: {psycopg}", "",
                "The above exception was the direct cause of the following exception:", "",
                "Traceback (most recent call last):", *loop_frame, *chain, f"sqlalchemy.exc.OperationalError: {message}"]
        self.emit(at, "\n".join(text))
        return at + self.s(0.0003, 0.001)

    def task_error(self, at, name, project_id, exc_lines, message):
        """An exception escaping a job for one project, caught by scheduled_project_task."""
        kwargs = f"{{'db_session': <sqlalchemy.orm.session.Session object at {self.addr()}>, 'project': <Project #{project_id}>}}"
        self.rec(at, "ERROR", f"Error trying to execute task: {name} with parameters () and {kwargs}",
                 "decorators.py", "_execute_task_in_project_context", "with parameters {args} and {kwargs}")
        record = self.src.rec("ERROR", message, "decorators.py", "_execute_task_in_project_context", "log.exception(e)",
                              after="with parameters {args} and {kwargs}")
        frame = self.src.frame("decorators.py", "_execute_task_in_project_context", "func(*args, **kwargs)",
                               after="def _execute_task_in_project_context")
        self.emit(at, "\n".join([record, "Traceback (most recent call last):", *frame, *exc_lines]))

    def slack_api_error(self, method, error):
        return f"The request to the Slack API failed. (url: {SLACK_URL.format(method)})\nThe server responded with: {{'ok': False, 'error': '{error}'}}"

    def slack_frames(self, api_call_frame):
        members, api_call, sync_send, urllib_call, validate = SLACK_SDK_LINES[self.src.slack_sdk]
        out = []
        if api_call_frame:
            out += render_frame(f"{SITE}/slack_sdk/web/client.py", members, "conversations_members",
                                '        return self.api_call("conversations.members", http_verb="GET", params=kwargs)',
                                hl='self.api_call("conversations.members", http_verb="GET", params=kwargs)')
        out += render_frame(f"{SITE}/slack_sdk/web/base_client.py", api_call, "api_call",
                            "            return self._sync_send(api_url=api_url, req_args=req_args)",
                            hl="self._sync_send(api_url=api_url, req_args=req_args)")
        out += render_frame(f"{SITE}/slack_sdk/web/base_client.py", sync_send, "_sync_send",
                            "        return self._urllib_api_call(", hl="self._urllib_api_call(", eol=True)
        out += render_frame(f"{SITE}/slack_sdk/web/base_client.py", urllib_call, "_urllib_api_call",
                            "        ).validate()", hl="validate()")
        out += render_frame(f"{SITE}/slack_sdk/web/slack_response.py", validate, "validate",
                            "            raise e.SlackApiError(message=msg, response=self)")
        return out

    def lookup_failed(self, at, user):
        """users.lookupByEmail for someone who left: make_call warns, does_user_exist() says no (cached per process)."""
        src = self.src
        record = src.rec("WARNING", f"SlackApiError for Slack API. Endpoint: users.lookupByEmail. Kwargs: {{'email': '{user}'}}",
                         "plugins/dispatch_slack/service.py", "make_call", "for Slack API. Endpoint: {endpoint}")
        frame = src.frame("plugins/dispatch_slack/service.py", "make_call", 'return client.api_call(endpoint, http_verb="GET", params=kwargs)',
                          hl='client.api_call(endpoint, http_verb="GET", params=kwargs)')
        message = self.slack_api_error("users.lookupByEmail", "users_not_found")
        self.emit(at, "\n".join([record, "Traceback (most recent call last):", *frame, *self.slack_frames(False),
                                 f"slack_sdk.errors.SlackApiError: {message}"]))

    # -- case jobs (case/scheduled.py)

    def reminder_day(self, at):
        return at.isoweekday() == self.src.reminder_weekday

    def cases(self, project, at, *statuses):
        return [c for c in self.w.cases if c.project == project and c.status(at) in statuses]

    def send_case_close_reminder(self, case, at):
        if case.assignee is None:
            self.rec(at, "WARNING", f"Case close reminder message not sent. No assignee for {case.name}.",
                     "case/messaging.py", "send_case_close_reminder", "Case close reminder message not sent. No assignee")
            return at + self.s(0.002, 0.006)
        at = self.slack(at + self.s(0.004, 0.012), "send_direct")
        self.rec(at, "DEBUG", f"Case close reminder sent to {case.assignee}.", "case/messaging.py", "send_case_close_reminder",
                 'log.debug(f"Case close reminder sent to')
        self.w.close_reminders.append((at, case))
        return at + self.s(0.0005, 0.002)

    def none_timestamp(self, at, func, attr):
        """`datetime.utcnow() - case.<attr>` on a case that never got the timestamp; the job logs it and moves on."""
        record = self.src.rec("ERROR", "unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'",
                              "case/scheduled.py", func, "log.exception(e)", after=f"def {func}")
        frame = self.src.frame("case/scheduled.py", func, f"span = datetime.utcnow() - case.{attr}", after=f"def {func}",
                               hl=f"datetime.utcnow() - case.{attr}", binop=(18, 1))
        self.emit(at, "\n".join([record, "Traceback (most recent call last):", *frame,
                                 "TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'"]))

    def case_close_reminder(self, at):
        for project, _ in PROJECTS:
            at += self.s(0.006, 0.03)
            for case in self.cases(project, at, "Triage"):
                if case.triage_at is None:
                    at += self.s(0.0005, 0.002)
                    self.none_timestamp(at, "case_close_reminder", "triage_at")
                    continue
                if (at - case.triage_at).days // 7 >= 1 and self.reminder_day(at):
                    at = self.send_case_close_reminder(case, at)
        return at

    def case_triage_reminder(self, at):
        for project, _ in PROJECTS:
            at += self.s(0.008, 0.035)
            for case in self.w.cases:
                status = case.status(at)
                if case.project != project or status in (None, "Closed"):
                    continue
                if not (case.title == "Security Event Triage" or status == "New") or (at - case.created).days < 1:
                    continue
                if case.assignee is None:
                    at += self.s(0.002, 0.006)
                    self.rec(at, "WARNING", f"Case triage reminder message not sent. No assignee for {case.name}.",
                             "case/messaging.py", "send_case_triage_reminder", "Case triage reminder message not sent. No assignee")
                    continue
                at += self.s(0.004, 0.012)
                if case.assignee == email("j.ramirez") and self.pod.name not in self.w.lookup_cached:
                    # send_direct() looks the user up first; the answer is cached for the life of the process
                    self.w.lookup_cached.add(self.pod.name)
                    began = at
                    at += self.s(0.15, 0.4)
                    self.lookup_failed(at, case.assignee)
                    at += self.s(0.0005, 0.002)
                    self.timer(at, "dispatch.plugins.dispatch_slack.plugin.SlackConversationPlugin.send_direct", (at - began).total_seconds())
                    at += self.s(0.0001, 0.0006)
                else:
                    at = self.slack(at, "send_direct")
                self.rec(at, "DEBUG", f"Case triage reminder sent to {case.assignee}.", "case/messaging.py", "send_case_triage_reminder",
                         'log.debug(f"Case triage reminder sent to')
                self.w.triage_reminders.append((at, case))
        return at

    def case_stable_reminder(self, at):
        for project, _ in PROJECTS:
            at += self.s(0.005, 0.025)
            for case in self.cases(project, at, "Stable"):
                if case.stable_at is None:
                    if self.src.stable_guard:
                        continue
                    at += self.s(0.0005, 0.002)
                    self.none_timestamp(at, "case_stable_reminder", "stable_at")
                    continue
                if (at - case.stable_at).days // 7 >= 1 and self.reminder_day(at):
                    at = self.send_case_close_reminder(case, at)
        return at

    # -- case and incident costs

    def calculate_cases_response_cost(self, at):
        slow = SLOW_COST_RUN <= at < SLOW_COST_RUN + timedelta(hours=1)
        for project, _ in PROJECTS:
            at += self.s(0.01, 0.04)
            for case in self.cases(project, at, "New", "Triage", "Stable"):
                if case.status(at) == "Stable" and case.stable_at is not None:
                    continue  # cost already updated after it went stable
                at += self.s(20, 40) if slow else self.s(0.01, 0.035)
                self.rec(at, "DEBUG", "No case cost model found. Skipping this case.", "case_cost/service.py",
                         "update_case_participant_activities", "No case cost model found")
                at += self.s(0.01, 0.05)
        return at

    def calculate_incidents_response_cost(self, at):
        at += self.s(0.004, 0.012)
        for inc in self.w.incidents:
            status = inc.status(at)
            if status in ("Active", "Stable"):
                at += self.s(0.01, 0.04)
                self.rec(at, "DEBUG", "No incident cost model found. Defaulting to classic incident cost model.",
                         "incident_cost/service.py", "calculate_incident_response_cost", "No incident cost model found")
            at += self.s(0.004, 0.015)
        return at + self.s(0.004, 0.012)  # the security project has no incidents

    # -- hourly "no plugin" jobs

    def per_project(self, at, level, template, path, func, anchor):
        for project, _ in PROJECTS:
            at += self.s(0.004, 0.015)
            self.rec(at, level, template.format(p=project), path, func, anchor)
        return at

    def sync_sources(self, at):
        return self.per_project(at, "DEBUG", "Data sources not synced. No source plugin enabled. Project: {p}. Organization: default",
                                "data/source/scheduled.py", "sync_sources", "Data sources not synced")

    def incident_auto_tagger(self, at):
        return self.per_project(at, "WARNING", "Incident tags not updated. No storage plugin enabled. Project: {p}. Organization: default",
                                "incident/scheduled.py", "incident_auto_tagger", "Incident tags not updated")

    def sync_tags(self, at):
        return self.per_project(at, "WARNING", "Tags not synced using external sources. No tag plugin enabled. Project: {p}. Organization: default",
                                "tag/scheduled.py", "sync_tags", "Tags not synced using external sources")

    def sync_terms(self, at):
        return self.per_project(at, "WARNING", "Skipping syncing terms. No term plugin enabled. Project: {p}. Organization: default",
                                "term/scheduled.py", "sync_terms", "Skipping syncing terms")

    def create_incident_tasks_reminders(self, at):
        return self.per_project(at, "DEBUG", "Overdue tasks in {p} project that need reminders: 0",
                                "task/scheduled.py", "create_incident_tasks_reminders", "Overdue tasks in")

    def sync_document_terms(self, at):
        return self.per_project(at, "WARNING", "Document terms not synced. No storage plugin enabled. Project: {p}. Organization: default",
                                "document/scheduled.py", "sync_document_terms", "Document terms not synced")

    def sync_incident_tasks_daily(self, at):
        return self.per_project(at, "WARNING", "Daily incident tasks sync skipped. No task plugin enabled. Project: {p}. Organization: default",
                                "task/scheduled.py", "sync_incident_tasks_daily", "Daily incident tasks sync skipped")

    def build_tag_models(self, at):
        for project, _ in PROJECTS:
            at += self.s(0.01, 0.04)
            self.rec(at, "DEBUG", f"Building the incident tag recommendation models for project {project}...",
                     "tag/scheduled.py", "build_tag_models", "Building the incident tag recommendation models")
            at += self.s(0.8, 2.6) if project == "default" else self.s(0.02, 0.08)
            self.rec(at, "DEBUG", "Successfully built the incident tag recommendation models.",
                     "tag/scheduled.py", "build_tag_models", "Successfully built the incident tag recommendation models")
        return at

    # -- incident jobs

    def incident_sync_members(self, at):
        at += self.s(0.005, 0.02)
        for inc in self.w.incidents:
            if inc.status(at) not in ("Active", "Stable"):
                continue
            if any(lo <= at < hi for lo, hi in RATE_LIMITED):
                at += self.s(0.15, 0.5)
                frames = self.src.frame("incident/scheduled.py", "incident_sync_members", "conversation_members = plugin.instance.get_all_member_emails(",
                                        hl="plugin.instance.get_all_member_emails(", eol=True)
                frames += self.src.frame("decorators.py", "wrapper", "return func(*args, **kwargs)", after="def counter(func)", hl="func(*args, **kwargs)")
                frames += self.src.frame("decorators.py", "wrapper", "result = func(*args, **kwargs)", after="def timer(func)", hl="func(*args, **kwargs)")
                frames += self.src.frame("plugins/dispatch_slack/plugin.py", "get_all_member_emails", "member_ids = client.conversations_members(",
                                         hl="client.conversations_members(channel=conversation_id)")
                message = self.slack_api_error("conversations.members", "ratelimited")
                frames += self.slack_frames(True) + [f"slack_sdk.errors.SlackApiError: {message}"]
                self.task_error(at, "dispatch.incident.scheduled.incident_sync_members", 1, frames, message)
                break  # the exception ends the job for this project
            at = self.slack(at, "get_all_member_emails", 0.35, 1.6)
        return at + self.s(0.003, 0.01)

    def incident_report_reminders(self, at):
        at += self.s(0.005, 0.02)
        for inc in self.w.incidents:
            if inc.status(at) != "Active":
                continue
            for kind in ("tactical", "executive"):
                last = max([inc.created] + [r for r in inc.reports[kind] if r <= at])
                if any(req <= at < due and k == kind for req, due, k in inc.delayed):
                    continue
                hours = int((at - last).total_seconds() // 3600)
                if hours >= inc.every[kind] and hours % inc.every[kind] == 0:
                    recent = [r for r in inc.reports["tactical"] if r <= at]
                    if recent and at - max(recent) < timedelta(hours=1):
                        continue
                    at = self.report_reminder(inc, at)
        return at

    def report_reminder(self, inc, at):
        at = self.command_name(at + self.s(0.002, 0.008))
        at = self.slack(at, "send_direct")
        self.rec(at, "DEBUG", f"Incident report reminder sent to {inc.commander}.", "report/messaging.py",
                 "send_incident_report_reminder", "Incident report reminder sent to")
        return at

    def incident_report_delayed_reminders(self, at):
        at += self.s(0.004, 0.03)
        for inc in self.w.incidents:
            if inc.status(at) != "Active":
                continue
            for req, due, kind in inc.delayed:
                if due + timedelta(minutes=1) < at and (inc, due) not in self.w.delayed_sent:
                    self.w.delayed_sent.add((inc, due))
                    at = self.report_reminder(inc, at)
        return at

    def incident_report_daily(self, at):
        at += self.s(0.01, 0.04)
        day = timedelta(hours=24)
        listed = [i for i in self.w.incidents if i.status(at) == "Active" or (i.status(at) == "Stable" and at - i.stable_at < day)
                  or (i.status(at) == "Closed" and at - i.timeline[-1][0] < day)]
        if listed:
            at = self.slack(at + self.s(0.02, 0.08), "send", 0.4, 1.3)
        return at + self.s(0.002, 0.01)

    def incident_close_reminder(self, at):
        at += self.s(0.005, 0.02)
        for inc in self.w.incidents:
            if inc.status(at) == "Stable" and (at - inc.stable_at).days // 7 >= 1 and at.isoweekday() == 1:
                at = self.command_name(at + self.s(0.002, 0.006))
                at = self.slack(at, "send_direct")
                self.rec(at, "DEBUG", f"Incident close reminder sent to {inc.commander}.", "incident/messaging.py",
                         "send_incident_close_reminder", "Incident close reminder sent to")
        return at + self.s(0.002, 0.008)

    def incident_report_weekly(self, at):
        at += self.s(0.004, 0.012)
        self.rec(at, "WARNING", "Incident weekly reports not sent. No AI plugin enabled.", "incident/scheduled.py",
                 "incident_report_weekly", "Incident weekly reports not sent. No AI plugin enabled.")
        return at + self.s(0.002, 0.008)

    def create_evergreen_reminders(self, at):
        at += self.s(0.02, 0.06)
        if at.date() == datetime(2025, 8, 4).date():  # the default project's on-call team is due for review
            at = self.plugin(at, "dispatch.plugins.dispatch_google.gmail.plugin.GoogleGmailEmailPlugin.send", 0.6, 1.4)
        at += self.s(0.02, 0.06)
        self.rec(at, "WARNING", "Evergreen reminder not sent. No email plugin enabled. Project: {project.name}. Organization: {project.organization.name}",
                 "evergreen/scheduled.py", "create_evergreen_reminder", "Evergreen reminder not sent. No email plugin enabled.")
        return at + self.s(0.002, 0.008)

    def feedback_report_daily(self, at):
        at += self.s(0.01, 0.03)
        rng = random.Random(at.date().toordinal())  # who got feedback that day
        if rng.random() < 0.25:
            at = self.plugin(at + self.s(0.01, 0.03), "dispatch.plugins.dispatch_google.gmail.plugin.GoogleGmailEmailPlugin.send", 0.5, 1.2)
            self.rec(at, "DEBUG", f"Case feedback daily report sent to {email(rng.choice(ENG_TEAM))}.", "feedback/incident/messaging.py",
                     "send_case_feedback_daily_report", "Case feedback daily report sent to")
        at += self.s(0.01, 0.03)
        for _ in range(rng.choice([0, 0, 1, 1, 2])):
            at += self.s(0.003, 0.01)
            self.rec(at, "WARNING", "Case feedback daily report not sent. Email plugin is not enabled.", "feedback/incident/messaging.py",
                     "send_case_feedback_daily_report", "Case feedback daily report not sent. Email plugin is not enabled.")
        return at + self.s(0.002, 0.008)

    def oncall_warning(self, at):
        self.rec(at, "WARNING", "Skipping collection of oncall shift feedback for project security. No oncall plugin enabled.",
                 "feedback/service/scheduled.py", "oncall_shift_feedback", "Skipping collection of oncall shift feedback")

    def oncall_shift_feedback_ucan(self, at):
        pd = "dispatch.plugins.dispatch_pagerduty.plugin.PagerDutyOncallPlugin."
        at = self.plugin(at + self.s(0.01, 0.03), pd + "get_schedule_id_from_service_id", 0.2, 0.7)
        at = self.plugin(at, pd + "did_oncall_just_go_off_shift", 0.3, 0.9)
        if at.isoweekday() == 2:  # weekly handoff: the outgoing on-call is asked for shift feedback
            at = self.slack(at + self.s(0.05, 0.2), "send_direct")
        for _ in range(2):  # the 12-hour and the 24-hour pass
            at += self.s(0.003, 0.01)
            self.oncall_warning(at)
        return at + self.s(0.002, 0.008)

    def oncall_shift_feedback_emea(self, at):
        at += self.s(0.01, 0.03)
        self.oncall_warning(at)
        return at + self.s(0.002, 0.008)


# --- the API --------------------------------------------------------------------------------------------

class Api:
    """One web pod: uvicorn's lines and the little the app logs at WARN."""

    PHRASES = {200: "OK", 201: "Created", 304: "Not Modified", 401: "Unauthorized", 404: "Not Found", 500: "Internal Server Error"}

    def __init__(self, world, pod):
        self.w, self.pod, self.src, self.rng, self.log = world, pod, pod.src, world.rng, world.api_log
        assets = random.Random(pod.sha)
        tag = lambda: "".join(assets.choice("0123456789abcdefABCDEFghijkmnpqrstuvwxyz_-") for _ in range(8))
        self.assets = [f"/assets/index-{tag()}.js", f"/assets/index-{tag()}.css", f"/assets/vendor-{tag()}.js",
                       f"/assets/vuetify-{tag()}.js", f"/assets/CaseTable-{tag()}.js", f"/assets/materialdesignicons-webfont-{tag()}.woff2"]

    def emit(self, at, text):
        self.log.emit(at, self.pod.name, text)

    def start(self):
        at = self.pod.started
        self.emit(at, f"[kubelet] Started container web (image {IMAGE.format(self.pod.sha[:8])})")
        at += timedelta(milliseconds=2600 + self.rng.randint(0, 400))
        for line in STARLETTE_WARNING:
            self.emit(at, line)
        at += timedelta(milliseconds=5200 + self.rng.randint(0, 900))  # plugins load at import, logged below WARN
        for line in ("Started server process [1]", "Waiting for application startup.", "Application startup complete."):
            self.emit(at, f"INFO:     {line}")
            at += timedelta(microseconds=self.rng.randint(200, 1500))
        self.emit(at, "INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)")

    def stop(self):
        at = self.pod.stopped
        for line in ("Shutting down", "Waiting for application shutdown.", "Application shutdown complete.", "Finished server process [1]"):
            self.emit(at, f"INFO:     {line}")
            at += timedelta(milliseconds=self.rng.randint(1, 40))

    def access(self, at, method, path, status, client):
        if self.w.db_down(at) and path.startswith("/api/v1/"):
            status = 500
            self.db_error(at)
        self.emit(at, f'INFO:     {client} - "{method} {path} HTTP/1.1" {status} {self.PHRASES[status]}')

    def db_error(self, at):
        kind = "starting" if self.w.db_error_kind(at, 1) == "starting" else "refused"
        message = f"(psycopg2.OperationalError) {PG_ERRORS[kind]}\n{SQLA_BACKGROUND}"
        main = "main.py"
        f = self.src.frame
        frames = (f(main, "dispatch", "response = await call_next(request)", after="class ExceptionMiddleware", hl="await call_next(request)")
                  + lib(STARLETTE_CALL_NEXT) + lib(STARLETTE_DISPATCH)
                  + f(main, "dispatch", "raise e from None", after="class MetricsMiddleware")
                  + f(main, "dispatch", "response = await call_next(request)", after="class MetricsMiddleware", hl="await call_next(request)")
                  + lib(STARLETTE_CALL_NEXT) + lib(SENTRY_ASGI) + lib(STARLETTE_DISPATCH)
                  + f(main, "db_session_middleware", "raise e from None", after="async def db_session_middleware")
                  + f(main, "db_session_middleware", "schema_names = inspect(engine).get_schema_names()", hl="inspect(engine)")
                  + lib(SQLA_INSPECT) + lib(SQLA_CONNECT_WRAP) + lib(SQLA_CONNECT_HEAD) + lib(SQLA_POOL_NEW) + lib(SQLA_CONNECT_TAIL))
        self.emit(at - timedelta(milliseconds=self.rng.randint(2, 9)),
                  "\n".join([f"ERROR:dispatch.main:{message}", "Traceback (most recent call last):", *frames, f"sqlalchemy.exc.OperationalError: {message}"]))


def axios_query(params):
    """Query string the way the UI's axios builds it."""
    def enc(value):
        out = quote(str(value), safe="-_.!~*'()")
        for a, b in (("%3A", ":"), ("%24", "$"), ("%2C", ","), ("%20", "+"), ("%5B", "["), ("%5D", "]")):
            out = out.replace(a, b)
        return out
    parts = []
    for key, value in params:
        parts.append(f"{key}={enc(value)}")
    return "&".join(parts)


class Traffic:
    """Requests reaching the web pods through the ingress controller."""

    INGRESS = ["10.42.1.23", "10.42.2.17", "10.42.3.9"]

    def __init__(self, world):
        self.w, self.rng = world, world.rng

    def client(self):
        return f"{self.rng.choice(self.INGRESS)}:{self.rng.randint(32768, 60999)}"

    def table_query(self, at, project_id, statuses, assignee=None, page=1):
        expr = [{"or": [{"model": "Project", "field": "id", "op": "==", "value": project_id}]}]
        if statuses:
            expr.append({"or": [{"model": "Case", "field": "status", "op": "==", "value": s} for s in statuses]})
        if assignee:
            expr.append({"or": [{"model": "Assignee", "field": "email", "op": "==", "value": assignee}]})
        params = [("q", ""), ("page", page), ("itemsPerPage", 25), ("sortBy[]", "reported_at"), ("descending[]", "true"),
                  ("filter", json.dumps({"and": expr}, separators=(",", ":")))]
        return "/api/v1/default/cases?" + axios_query(params)

    def session(self, api, at, user):
        """A person opening the UI and clicking around: bursts of requests separated by reading time."""
        r = self.rng
        client = self.client()
        open_cases = [c for c in self.w.cases if c.status(at) not in (None, "Closed")]
        groups = []
        if r.random() < 0.7:
            load = [("GET", r.choice(["/default/cases", "/default/cases", "/default/signals", "/default/incidents", "/"]), 200)]
            cached = r.random() < 0.6
            load += [("GET", asset, 304 if cached else 200) for asset in api.assets]
            if not cached:
                load.append(("GET", "/favicon.ico", 200))
            if r.random() < 0.04:
                load += [("GET", "/api/v1/default/auth/me", 401),
                         ("GET", f"/implicit/callback?code={r.getrandbits(80):020x}&state={r.getrandbits(64):016x}", 200)]
            load += [("GET", "/api/v1/default/auth/me", 200), ("GET", "/api/v1/default/auth/myrole", 200),
                     ("GET", "/api/v1/organizations?q=&page=1&itemsPerPage=50", 200),
                     ("GET", "/api/v1/default/projects?q=&page=1&itemsPerPage=-1", 200)]
            groups.append(load)
        for _ in range(r.randint(1, 5)):
            pick, click = r.random(), []
            if pick < 0.45:
                project_id = r.choice([2, 2, 2, 1])
                statuses = r.choice([["New", "Triage"], ["New", "Triage", "Escalated"], [], ["Stable"], ["New"]])
                click.append(("GET", self.table_query(at, project_id, statuses, email(user) if r.random() < 0.25 else None), 200))
                if r.random() < 0.15:
                    groups.append(click)
                    click = [("GET", self.table_query(at, project_id, statuses, page=2), 200)]
            elif pick < 0.85 and open_cases:
                case = r.choice(open_cases)
                instances = json.dumps({"and": [{"model": "Case", "field": "id", "op": "==", "value": case.id}]}, separators=(",", ":"))
                click += [("GET", f"/api/v1/default/cases/{case.id}", 200),
                          ("GET", f"/api/v1/default/cases/{case.id}/participants?minimal=true", 200),
                          ("GET", "/api/v1/default/signals/instances?" + axios_query([("q", ""), ("page", 1), ("itemsPerPage", 10), ("filter", instances)]), 200)]
                if r.random() < 0.08:
                    groups.append(click)
                    click = [("GET", "/api/v1/default/case_types?q=&page=1&itemsPerPage=50", 200),
                             ("GET", "/api/v1/default/case_priorities?q=&page=1&itemsPerPage=50", 200),
                             ("GET", "/api/v1/default/case_severities?q=&page=1&itemsPerPage=50", 200)]
                    groups.append(click)
                    click = [("PUT", f"/api/v1/default/cases/{case.id}", 200), ("GET", f"/api/v1/default/cases/{case.id}", 200)]
            elif pick < 0.93:
                click.append(("GET", "/api/v1/default/incidents?q=&page=1&itemsPerPage=10&sortBy[]=reported_at&descending[]=true", 200))
            else:
                click.append(("GET", "/api/v1/default/signals/instances?q=&page=1&itemsPerPage=25&sortBy[]=created_at&descending[]=true", 200))
            if click:
                groups.append(click)
        t = at
        for group in groups:
            for method, path, status in group:
                t += timedelta(milliseconds=r.randint(8, 120) if path.startswith(("/assets", "/favicon")) else r.randint(20, 450))
                yield t, method, path, status, client
            t += timedelta(seconds=r.uniform(3, 75))

    def slack_events(self, day):
        """Events API, interactivity and slash commands posted by Slack."""
        r = self.rng
        weekday = day.isoweekday() < 6
        for _ in range(r.randint(45, 90) if weekday else r.randint(8, 20)):
            at = day + timedelta(hours=r.uniform(6, 24) if r.random() < 0.85 else r.uniform(0, 6))
            yield at, "POST", "/api/v1/default/events/slack/event", 200, self.client()
        for _ in range(r.randint(8, 25) if weekday else r.randint(0, 4)):
            at = day + timedelta(hours=r.uniform(7, 24))
            yield at, "POST", r.choice(["/api/v1/default/events/slack/action", "/api/v1/default/events/slack/action", "/api/v1/default/events/slack/command"]), 200, self.client()

    def generate(self, pods):
        users = SEC_TEAM + ENG_TEAM
        requests = []
        day = START
        while day < END:
            weekday = day.isoweekday() < 6
            for _ in range(self.rng.randint(54, 72) if weekday else self.rng.randint(8, 16)):
                if self.rng.random() < 0.35:
                    at = day + timedelta(hours=self.rng.uniform(7, 16))
                else:
                    at = day + timedelta(hours=self.rng.uniform(14, 24.9))
                requests += list(self.session_for(pods, at, self.rng.choice(users)))
            requests += list(self.slack_events(day))
            day += timedelta(days=1)
        # the bulk close of the misfired cases on Monday afternoon: the UI fetches each case, then PUTs them all at once
        at = datetime(2025, 8, 11, 15, 30, 40, tzinfo=UTC)
        requests.append((at, "GET", self.table_query(at, 2, ["New"]), 200, self.client()))
        fetched = self.w.burst[0].timeline[-1][0] - timedelta(milliseconds=900)
        for case in self.w.burst:
            fetched += timedelta(milliseconds=self.rng.randint(8, 40))
            requests += [(fetched, "GET", f"/api/v1/default/cases/{case.id}", 200, self.client()),
                         (case.timeline[-1][0], "PUT", f"/api/v1/default/cases/{case.id}", 200, self.client())]
        # people acting on their Slack reminders
        for at, _ in self.w.close_reminders + self.w.triage_reminders:
            if self.rng.random() < 0.35:
                requests.append((at + timedelta(minutes=self.rng.uniform(1, 120)), "POST", "/api/v1/default/events/slack/action", 200, self.client()))
        requests.sort(key=lambda req: req[0])
        for req in requests:
            api = next((a for a in pods if a.pod.started + timedelta(seconds=9) <= req[0] < a.pod.stopped), None)
            if api is not None:
                api.access(*req)

    def session_for(self, pods, at, user):
        api = next((a for a in pods if a.pod.started <= at < a.pod.stopped), pods[-1])
        return self.session(api, at, user)


# --- putting it together ------------------------------------------------------------------------------

class World:
    def __init__(self, rng):
        self.rng = rng
        self.cases, self.burst = build_cases(rng)
        self.incidents = build_incidents()
        self.scheduler_log, self.api_log = Log(), Log()
        self.close_reminders, self.triage_reminders = [], []
        self.lookup_cached, self.delayed_sent = set(), set()

    @staticmethod
    def db_down(at):
        return DB_OUTAGE[0] <= at < DB_OUTAGE[1]

    @staticmethod
    def db_error_kind(at, failures_so_far):
        if at >= DB_OUTAGE[1] - timedelta(seconds=55):
            return "starting"
        return "closed" if failures_so_far == 0 else "refused"


def main():
    build = Path(sys.argv[1])
    rng = random.Random(20250818)
    fixture = build / "fixture.git"
    q4 = json.loads((build / "plants.json").read_text())["plants"][PLANT]

    shas = [deployed_commit(fixture, d) for d in [EARLIER_DEPLOY] + DEPLOYS]
    sources = [Source(fixture, sha, q4) for sha in shas]
    assert [s.has_q4 for s in sources] == [False, False, True], "only the second rollout in the window may ship q4"

    world = World(rng)
    starts = [EARLIER_DEPLOY] + DEPLOYS
    templates = {d: ["".join(rng.choice(POD_CHARS) for _ in range(n)) for n in (9, 10, 9)] for d in ("scheduler", "web")}
    pods = {}
    for deployment, drain in (("scheduler", 27), ("web", 41)):
        pods[deployment] = []
        for i, (started, sha, src) in enumerate(zip(starts, shas, sources)):
            started += timedelta(seconds=0 if deployment == "scheduler" else rng.uniform(0.8, 3.5))
            stopped = starts[i + 1] + timedelta(seconds=drain + rng.uniform(0, 6)) if i + 1 < len(starts) else END + timedelta(days=1)
            pods[deployment].append(Pod(rng, deployment, templates[deployment][i], started, stopped, sha, src))

    for pod in pods["scheduler"]:
        Scheduler(world, pod).run()
    apis = [Api(world, pod) for pod in pods["web"]]
    for api in apis:
        api.start()
        if api.pod.stopped < END:
            api.stop()
    Traffic(world).generate(apis)

    out = build / "data" / "log-reminders-stopped"
    for name, log in (("scheduler.log", world.scheduler_log), ("api.log", world.api_log)):
        log.write(out / name)
        size = (out / name).stat().st_size
        print(f"{name}: {len(log.lines)} lines, {size / 1e6:.2f} MB")
    print(f"images {[sha[:8] for sha in shas[1:]]} (running at start: {shas[0][:8]}) -> {out}")


if __name__ == "__main__":
    main()
