"""Generates the logs of the mt-logs-case-cost task (pilot 4).

Three weeks (2025-08-25 to 2025-09-14) of what three sources in the `dispatch` namespace write:

- scheduler.log: `dispatch scheduler start`, at LOG_LEVEL=DEBUG. The image's sitecustomize sets
  up the root logger before Dispatch does (so Dispatch's own basicConfig is a no-op) with
  `%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s`, UTC; third-party loggers
  stay at WARNING. Jobs run in the scheduler's thread pool (`Thread-N (worker)`).
- cost-sync.log: case-cost-sync, the finance team's hourly CronJob that copies each case's
  classic response cost from Dispatch's API into the finance warehouse, logs every change, and
  flags for review any cost that rose by more than half (and more than $500) since its last sync.
- events.log: the Kubernetes events of the namespace, as the event exporter writes them: rollouts
  (with the image each pod pulls), the CronJob's pods, autoscaling, a node drain.

Plant q2 (the classic cost of a case stops at the latest of its escalated/stable/closed times
instead of the earliest) reaches production with the rollout of 2025-09-02. The hourly case cost
job only recomputes a stable case once, the first hour after it is marked stable, so the bug
shows when a case that was escalated (or closed) earlier is marked stable: its cost then counts
the whole escalation, and case-cost-sync flags it. Before that rollout, the same transition
barely moved the cost. Separately, a project created on 2025-09-08 has no annual employee cost
(NULL), so from then on every hourly case cost run logs a TypeError for each of its open cases.

The noise is drawn from what the deployed code really logs, with the costs computed by the same
formula as the code each pod runs and traceback line numbers taken from that commit. Seeded, so
the files are identical on every build.

Usage: python3 -I fixture/gen_logs_pilot4.py <build dir>
Reads <build>/fixture.git and <build>/plants.json,
writes <build>/data/mt-logs-case-cost/{scheduler,cost-sync,events}.log
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import json
import math
import random
import subprocess
from datetime import datetime, timedelta, timezone

import gen_logs_pilot2 as p2  # traceback renderer, SQLAlchemy/psycopg2 frames, perf_counter spans

UTC = timezone.utc
TASK = "mt-logs-case-cost"
PLANT = "q2-case-cost-cutoff"
START = datetime(2025, 8, 25, tzinfo=UTC)
END = datetime(2025, 9, 15, tzinfo=UTC)
WARM = datetime(2025, 7, 8, tzinfo=UTC)  # cases and costs are simulated from here on; nothing is written before START
EARLIER_DEPLOY = datetime(2025, 8, 20, 16, 31, 7, tzinfo=UTC)  # running when the window opens
DEPLOYS = [datetime(2025, 8, 27, 17, 2, 44, tzinfo=UTC), datetime(2025, 9, 2, 18, 14, 9, tzinfo=UTC),
           datetime(2025, 9, 4, 16, 52, 30, tzinfo=UTC)]
SHIPS_PLANT = 1  # index in DEPLOYS of the first rollout whose image contains the plant
NODE_DRAIN = datetime(2025, 9, 10, 3, 12, 5, tzinfo=UTC)  # the scheduler's node is drained; same image restarts elsewhere
DB_FAILOVER = (datetime(2025, 9, 6, 3, 53, 20, tzinfo=UTC), datetime(2025, 9, 6, 3, 54, 52, tzinfo=UTC))  # RDS Multi-AZ failover
SYNC_UPGRADE = datetime(2025, 9, 1, 10, 20, tzinfo=UTC)  # case-cost-sync 1.4.2 -> 1.5.0
SYNC_TIMEOUT = datetime(2025, 8, 31, 7, 20, tzinfo=UTC)  # one page read times out and is retried
FRAUD_CREATED = datetime(2025, 9, 8, 14, 47, 12, tzinfo=UTC)
FIRST_PULL_FAILS = DEPLOYS[0]  # the registry answers 502 to one web pod's first pull

SITE = p2.SITE
IMAGE = "registry.example.com/dispatch:main-{}"
SYNC_IMAGE = "registry.example.com/finance/case-cost-sync:{}"
BACKUP_IMAGE = "registry.example.com/platform/pg-backup:2.3.1"
POD_CHARS = p2.POD_CHARS
NODES = ["ip-10-20-1-17.ec2.internal", "ip-10-20-2-88.ec2.internal", "ip-10-20-3-41.ec2.internal"]
SPARE_NODE = "ip-10-20-4-102.ec2.internal"  # joins when ip-10-20-3-41 is drained
DISPATCH_HOST = "dispatch.internal.example.com"
WAREHOUSE = "finance-dw.internal.example.com:5439/finance"
ORG = "default"

SEC_TEAM = ["a.chen", "m.okafor", "s.lindqvist", "r.patel", "d.moreau", "k.tanaka"]
ENG_TEAM = ["l.nguyen", "p.walsh", "t.becker"]
FRAUD_TEAM = ["j.ortiz", "h.mbeki"]
SIGNAL_TITLES = p2.SIGNAL_TITLES
ENG_TITLES = p2.ENG_TITLES
FRAUD_TITLES = ["Card testing from a single BIN", "Refund abuse pattern", "Account takeover: payout change",
                "Promo code farming", "Chargeback spike on one merchant"]


def email(user):
    return f"{user}@example.com"


def asctime(at):
    return at.strftime("%Y-%m-%d %H:%M:%S,") + f"{at.microsecond // 1000:03d}"


def iso_ms(at):
    return at.strftime("%Y-%m-%dT%H:%M:%S.") + f"{at.microsecond // 1000:03d}+00:00"


def iso_s(at):
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


def git(fixture, *args):
    return subprocess.run(["git", "-C", str(fixture), *args], check=True, capture_output=True, text=True).stdout


def deployed_commit(fixture, when):
    """The newest commit on main at deploy time."""
    return git(fixture, "log", "-1", "--format=%H", f"--before={when.isoformat()}", "main").strip()


# --- the code a pod runs ------------------------------------------------------------------------------

class Source:
    """What one image ships: the cost cut-off, plugin entry points, traceback line numbers."""

    def __init__(self, fixture, sha, plant):
        self.fixture, self.sha, self.files = fixture, sha, {}
        self.has_plant = subprocess.run(["git", "-C", str(fixture), "merge-base", "--is-ancestor", plant, sha]).returncode == 0
        service = "\n".join(self.lines("case_cost/service.py"))
        # get_participant_role_time_seconds cuts the role's time at min() or max() of the case's timestamps
        self.latest_cut_off = "participant_role_renounced_at = max(timestamps)" in service
        assert self.latest_cut_off == self.has_plant
        assert "participant_role_time_hours = ((days * HOURS_IN_DAY) / 3) + hours" in service
        assert "return math.ceil(project.annual_employee_cost / project.business_year_hours)" in service
        self.plugins = p2.Source.entry_points(self)
        for path, anchor in MESSAGES:
            assert anchor in "\n".join(self.lines(path)), (path, anchor, sha[:8])

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

    def frame(self, path, func, anchor, after=None, **kw):
        n = self.find(path, anchor, after)
        return p2.render_frame(f"{SITE}/dispatch/{path}", n, func, self.lines(path)[n - 1], **kw)


# messages the generator writes, with the source line that logs each; checked against every image
MESSAGES = [
    ("common/utils/cli.py", 'logger.info(f"Attempting to load plugin: {ep.name}")'),
    ("common/utils/cli.py", 'logger.info(f"Successfully loaded plugin: {ep.name}")'),
    ("scheduler.py", 'log.info("Starting scheduler...")'),
    ("scheduler.py", 'log.debug("Stopping scheduler...")'),
    ("decorators.py", 'log.debug(f"function.elapsed.time.{fullname(func)}: {elapsed_time}")'),
    ("decorators.py", 'f"Error trying to execute task: {fullname(func)}"'),
    ("data/source/scheduled.py", 'f"Data sources not synced. No source plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("incident/scheduled.py", 'f"Incident tags not updated. No storage plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("incident/scheduled.py", 'log.warning("No conversation plugin is active.")'),
    ("incident/scheduled.py", 'log.warning("Incident weekly reports not sent. No AI plugin enabled.")'),
    ("tag/scheduled.py", 'f"Tags not synced using external sources. No tag plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("tag/scheduled.py", 'log.debug(f"Building the incident tag recommendation models for project {project.name}...")'),
    ("tag/scheduled.py", 'log.debug("Successfully built the incident tag recommendation models.")'),
    ("term/scheduled.py", 'f"Skipping syncing terms. No term plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("task/scheduled.py", 'log.debug(f"Overdue tasks in {project.name} project that need reminders: {len(overdue_tasks)}")'),
    ("task/scheduled.py", 'f"Daily incident tasks sync skipped. No task plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("document/scheduled.py", 'f"Document terms not synced. No storage plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("evergreen/scheduled.py", '"Evergreen reminder not sent. No email plugin enabled. Project: {project.name}. Organization: {project.organization.name}"'),
    ("feedback/service/scheduled.py", 'f"Skipping collection of oncall shift feedback for project {project.name}. No oncall plugin enabled."'),
    ("feedback/incident/messaging.py", 'log.warning("Case feedback daily report not sent. Email plugin is not enabled.")'),
    ("case/messaging.py", 'log.debug(f"Case triage reminder sent to {case.assignee.individual.email}.")'),
    ("case/messaging.py", 'log.warning("Case triage reminder message not sent. No conversation plugin enabled.")'),
    ("incident/messaging.py", 'log.debug(f"Incident close reminder sent to {incident.commander.individual.email}.")'),
    ("report/messaging.py", 'log.debug(f"Incident report reminder sent to {incident.commander.individual.email}.")'),
    ("case_cost/service.py", 'log.debug("No case cost model found. Skipping this case.")'),
    ("case_cost/scheduled.py", "log.exception(e)"),
    ("incident_cost/service.py", 'log.debug("No incident cost model found. Defaulting to classic incident cost model.")'),
]


# --- the world: projects, cases, incidents, costs -------------------------------------------------------

class Project:
    def __init__(self, pid, name, annual, hours, created=None, slack=True):
        self.id, self.name, self.annual, self.hours = pid, name, annual, hours
        self.created, self.slack = created, slack

    def exists(self, at):
        return self.created is None or self.created <= at

    @property
    def hourly_rate(self):
        """get_hourly_rate(); None stands for the TypeError a NULL setting raises."""
        if self.annual is None or self.hours is None:
            return None
        return math.ceil(self.annual / self.hours)


DEFAULT = Project(1, "default", 50000, 2080)
SECURITY = Project(2, "security", 200000, 2080)
FRAUD = Project(3, "fraud", None, 2080, created=FRAUD_CREATED, slack=False)  # created through the API with an empty cost field
PROJECTS = [DEFAULT, SECURITY, FRAUD]

STATUS_FLOWS = {  # what case_status_transition_flow_dispatcher stamps, by (previous, new) status
    ("New", "Triage"): ("triage",), ("Closed", "Triage"): ("triage",),
    ("New", "Escalated"): ("triage", "escalated"), ("Triage", "Escalated"): ("escalated",),
    ("New", "Closed"): ("triage", "closed"), ("Triage", "Closed"): ("closed",), ("Escalated", "Closed"): ("closed",),
    ("Stable", "Closed"): ("closed",),
    ("Escalated", "Stable"): ("stable",), ("Triage", "Stable"): ("stable",), ("New", "Stable"): ("triage", "stable"),
    ("Closed", "Stable"): ("stable",),
}
MULTIPLIER = {"Assignee": 1, "Reporter": 0.5, "Participant": 0.5, "Observer": 0}


class Case:
    def __init__(self, project, title, created, assignee):
        self.id = None
        self.project, self.title, self.created, self.assignee = project, title, created, assignee
        self.timeline = [(created, "New")]
        self.roles = []  # (role, assumed_at)
        if assignee:
            self.roles.append(("Assignee", created + timedelta(seconds=2)))

    @property
    def name(self):
        return f"dispatch-{ORG}-{self.project.name}-{self.id}"

    def move(self, at, status):
        self.timeline.append((at, status))

    def state(self, at):
        """Status and the triage/escalated/stable/closed timestamps as they stand at `at`."""
        status, stamps = None, {}
        for when, new in self.timeline:
            if when > at:
                break
            if status is not None:
                for stamp in STATUS_FLOWS.get((status, new), ()):
                    if stamp != "triage" or "triage" not in stamps:
                        stamps[stamp] = when
            status = new
        return status, stamps

    def status(self, at):
        return self.state(at)[0]


def role_seconds(role, assumed, cut):
    """get_participant_role_time_seconds() once the cut-off is known."""
    if MULTIPLIER[role] == 0:
        return 0
    hours = (cut - assumed).total_seconds() / 3600
    if hours < 0:
        return 0
    if hours > 24:
        days, rest = divmod(hours, 24)
        hours = ((days * 24) / 3) + rest
    return hours * 3600 * MULTIPLIER[role]


def classic_cost(case, at, latest_cut_off):
    """calculate_case_response_cost_classic() at `at`, by the image's cut-off rule."""
    status, stamps = case.state(at)
    cut = at
    if status not in ("New", "Triage"):
        times = [stamps[k] for k in ("stable", "escalated", "closed") if k in stamps]
        if times:
            cut = max(times) if latest_cut_off else min(times)
    total = 0
    for role, assumed in case.roles:
        if assumed <= at:
            total += role_seconds(role, assumed, cut)
    return math.ceil(math.ceil((total / 3600) * case.project.hourly_rate))


class Incident:
    def __init__(self, iid, project, title, commander, created, stable=None, closed=None):
        self.id, self.project, self.title, self.commander = iid, project, title, commander
        self.created, self.stable_at, self.closed_at = created, stable, closed

    def status(self, at):
        if at < self.created:
            return None
        if self.closed_at and at >= self.closed_at:
            return "Closed"
        if self.stable_at and at >= self.stable_at:
            return "Stable"
        return "Active"


def utc(*args):
    return datetime(2025, *args, tzinfo=UTC)


def build_world(rng):
    cases, incidents = [], []

    def add(project, title, created, user, roles=()):
        case = Case(project, title, created, email(user) if user else None)
        for role, after in roles:
            case.roles.append((role, created + after))
        cases.append(case)
        return case

    # cases escalated to an incident and later marked stable, and one closed case reopened as stable
    a = add(SECURITY, "AWS: Root account login", utc(8, 19, 9, 14, 27), "r.patel", [("Reporter", timedelta(seconds=1))])
    a.move(utc(8, 19, 11, 2, 40), "Triage")
    a.move(utc(8, 21, 15, 40, 12), "Escalated")
    a.move(utc(8, 28, 10, 5, 33), "Stable")
    a.move(utc(9, 1, 16, 20, 2), "Closed")
    b = add(SECURITY, "CrowdStrike: Malware detected", utc(8, 27, 22, 10, 51), "m.okafor", [("Reporter", timedelta(seconds=1))])
    b.move(utc(8, 28, 8, 30, 19), "Triage")
    b.move(utc(8, 29, 13, 12, 47), "Escalated")
    b.move(utc(9, 3, 10, 41, 5), "Stable")
    b.move(utc(9, 6, 9, 15, 44), "Closed")
    c = add(SECURITY, "Okta: Suspicious OAuth consent grant", utc(9, 1, 7, 55, 2), "s.lindqvist",
            [("Participant", timedelta(hours=3, minutes=12))])
    c.move(utc(9, 1, 9, 20, 31), "Triage")
    c.move(utc(9, 2, 11, 30, 8), "Escalated")
    c.move(utc(9, 5, 15, 2, 51), "Stable")
    c.move(utc(9, 9, 12, 1, 9), "Closed")
    d = add(SECURITY, "GitHub: Personal access token exposed", utc(8, 25, 14, 12, 38), "k.tanaka")
    d.move(utc(8, 25, 16, 40, 3), "Triage")
    d.move(utc(8, 29, 17, 3, 26), "Closed")
    d.move(utc(9, 8, 9, 47, 18), "Stable")  # the token was used again: reopened to watch it
    d.move(utc(9, 11, 12, 0, 37), "Closed")
    e = add(SECURITY, "Okta: Impossible travel", utc(9, 4, 8, 21, 45), "a.chen", [("Reporter", timedelta(seconds=1))])
    e.move(utc(9, 4, 10, 2, 13), "Triage")
    e.move(utc(9, 5, 16, 48, 29), "Escalated")
    e.move(utc(9, 9, 11, 15, 2), "Stable")
    e.move(utc(9, 12, 14, 30, 55), "Closed")
    f = add(SECURITY, "AWS: S3 bucket policy made public", utc(9, 8, 19, 40, 16), "d.moreau",
            [("Participant", timedelta(hours=14, minutes=2))])
    f.move(utc(9, 9, 8, 5, 41), "Triage")
    f.move(utc(9, 9, 14, 30, 12), "Escalated")
    f.move(utc(9, 12, 10, 20, 4), "Stable")
    escalated = {"A": a, "B": b, "C": c, "D": d, "E": e, "F": f}

    incidents.append(Incident(49, DEFAULT, "Elevated 5xx on api-gateway", email("l.nguyen"), utc(7, 7, 14, 2), utc(7, 9, 10, 31)))
    for iid, case, stable, closed in ((52, a, utc(8, 25, 11, 0, 4), utc(8, 27, 16, 3, 40)),
                                      (54, b, utc(9, 1, 9, 30, 11), utc(9, 3, 10, 30, 2)),
                                      (55, c, utc(9, 4, 14, 0, 27), utc(9, 5, 14, 45, 13)),
                                      (57, e, utc(9, 8, 10, 0, 50), utc(9, 9, 10, 50, 31)),
                                      (58, f, utc(9, 11, 16, 0, 8), None)):
        at = next(t for t, s in case.timeline if s == "Escalated")
        incidents.append(Incident(iid, SECURITY, case.title, case.assignee, at + timedelta(seconds=6), stable, closed))

    # the everyday flow of signal cases
    t = WARM
    while t < END:
        t += timedelta(hours=rng.expovariate(1 / 5.2))
        user = rng.choice(SEC_TEAM) if rng.random() > 0.03 else None
        roles = [("Reporter", timedelta(seconds=1))] if rng.random() < 0.3 else []
        case = add(SECURITY, rng.choice(SIGNAL_TITLES), t, user, roles)
        if rng.random() < 0.45:  # false positive, closed straight from New
            case.move(t + timedelta(hours=rng.uniform(0.4, 20)), "Closed")
            continue
        triage = t + timedelta(days=rng.uniform(0.05, 1.6))
        case.move(triage, "Triage")
        if rng.random() < 0.25:
            case.roles.append(("Participant", triage + timedelta(hours=rng.uniform(0.2, 9))))
        if rng.random() < 0.1:
            case.roles.append(("Observer", triage + timedelta(hours=rng.uniform(0.1, 3))))
        r = rng.random()
        done = triage + timedelta(days=rng.uniform(0.3, 3.5) if r < 0.8 else rng.uniform(7, 12) if r < 0.96 else rng.uniform(12, 19))
        if rng.random() < 0.15:
            case.move(done, "Stable")
            done += timedelta(days=rng.uniform(3, 10))
        case.move(done, "Closed")
    # requests to the engineering side wait days before anyone triages them
    t = WARM + timedelta(days=1, hours=15)
    while t < END:
        case = add(DEFAULT, rng.choice(ENG_TITLES), t, rng.choice(ENG_TEAM), [("Reporter", timedelta(seconds=1))])
        triage = t + timedelta(days=rng.uniform(2.2, 4.8))
        case.move(triage, "Triage")
        case.move(triage + timedelta(days=rng.uniform(0.2, 2.5)), "Closed")
        t += timedelta(days=rng.uniform(3.2, 4.6), hours=rng.uniform(-3, 3))
    # the fraud team's first cases, once its project exists
    t = FRAUD_CREATED + timedelta(minutes=44, seconds=28)
    while t < END:
        case = add(FRAUD, rng.choice(FRAUD_TITLES), t, rng.choice(FRAUD_TEAM), [("Reporter", timedelta(seconds=1))])
        triage = t + timedelta(hours=rng.uniform(5, 30))
        case.move(triage, "Triage")
        if rng.random() < 0.5:
            case.move(triage + timedelta(days=rng.uniform(0.8, 2.5)), "Closed")
        t += timedelta(hours=rng.uniform(9, 22))

    cases.sort(key=lambda case: case.created)
    next_id = 4811
    for case in cases:
        case.id = next_id
        next_id += rng.randint(1, 3)
    return cases, incidents, escalated


class CostRow:
    """The case's classic CaseCost row: amount and updated_at, and every value it held."""

    def __init__(self, at):
        self.amount, self.updated_at, self.history = 0, at, [(at, 0)]

    def set(self, at, amount):
        self.amount, self.updated_at = amount, at
        self.history.append((at, amount))

    def at(self, when):
        value = None
        for t, amount in self.history:
            if t > when:
                break
            value = amount
        return value


# --- logs --------------------------------------------------------------------------------------------

class Log:
    def __init__(self):
        self.lines = []

    def add(self, at, text):
        if START <= at < END:
            self.lines.append((at, len(self.lines), text))

    def write(self, path):
        self.lines.sort(key=lambda line: (line[0], line[1]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(text for _, _, text in self.lines) + "\n")


class Pod:
    def __init__(self, rng, name, started, stopped, sha, src):
        self.name, self.started, self.stopped, self.sha, self.src = name, started, stopped, sha, src
        self.uptime = rng.uniform(4e5, 3e6)  # perf_counter() of the node when the pod starts


def nodes_at(at):
    return NODES if at < NODE_DRAIN else NODES[:2] + [SPARE_NODE]


def suffix(rng, n=5):
    return "".join(rng.choice(POD_CHARS) for _ in range(n))


# --- the scheduler ------------------------------------------------------------------------------------

JOBS = [  # every job `dispatch scheduler start` runs, in import order, less the 30-second sync jobs it excludes
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
SLACK = "dispatch.plugins.dispatch_slack.plugin.SlackConversationPlugin."
PD = "dispatch.plugins.dispatch_pagerduty.plugin.PagerDutyOncallPlugin."
GMAIL = "dispatch.plugins.dispatch_google.gmail.plugin.GoogleGmailEmailPlugin.send"


def fullname(path, func):
    return "dispatch." + path[:-3].replace("/", ".") + "." + func


def module(path):
    return "dispatch." + path[:-3].replace("/", ".")


class Scheduler:
    """One scheduler pod: its startup, the jobs it runs, what they log, and the costs they write."""

    def __init__(self, world, pod):
        self.w, self.pod, self.src, self.rng, self.log = world, pod, pod.src, world.rng, world.scheduler_log
        self.thread = "MainThread"
        self.db_failures = 0

    def emit(self, at, level, name, message):
        self.log.add(at, f"{asctime(at)} {level} [{self.thread}] {name}: {message}")

    def raw(self, at, text):
        self.log.add(at, text)

    def s(self, lo, hi):
        return timedelta(seconds=self.rng.uniform(lo, hi))

    def timer(self, at, name, seconds):
        self.emit(at, "DEBUG", "dispatch.decorators", f"function.elapsed.time.{name}: {p2.elapsed(self.pod, at, seconds)}")

    def plugin(self, at, qualname, lo, hi):
        span = self.s(lo, hi)
        at += span
        self.timer(at, qualname, span.total_seconds())
        return at + self.s(0.0001, 0.0006)

    def projects(self, at):
        return [p for p in PROJECTS if p.exists(at)]

    # -- lifecycle

    def start(self):
        at = self.pod.started + timedelta(milliseconds=2400 + self.rng.randint(0, 300))
        for line in p2.STARLETTE_WARNING:
            self.raw(at, line)
        at += self.s(0.6, 0.9)
        for name in self.src.plugins:
            self.emit(at, "INFO", "dispatch.common.utils.cli", f"Attempting to load plugin: {name}")
            at += self.s(0.002, 0.35 if name.startswith(("dispatch_slack", "google", "slack")) else 0.06)
            self.emit(at, "INFO", "dispatch.common.utils.cli", f"Successfully loaded plugin: {name}")
            at += self.s(0.0002, 0.001)
        self.raw(at, "Starting scheduler...")
        self.emit(at + self.s(0.0001, 0.0003), "INFO", "dispatch.scheduler", "Starting scheduler...")
        return at

    def run(self):
        loop = self.start()
        reg = self.pod.started + timedelta(seconds=3.1)
        period = 1.0 + self.rng.uniform(0.0002, 0.0009)  # run_pending() then sleep(1)
        queue = [[p2.first_run(spec, reg), i, name, path, func, spec] for i, (name, path, func, spec) in enumerate(JOBS)]
        end = min(self.pod.stopped, END)
        while True:
            queue.sort(key=lambda job: (job[0], job[1]))
            offset = (queue[0][0] - loop).total_seconds()
            tick = loop + timedelta(seconds=math.ceil(offset / period) * period)
            if tick >= end:
                break
            for k, job in enumerate([job for job in queue if job[0] <= tick]):
                at = tick + timedelta(microseconds=170 * k + self.rng.randint(15, 90))
                self.dispatch(job[2], job[3], job[4], at)
                job[0] = p2.next_run(job[5], at, self.rng)
        if self.pod.stopped < END:
            self.thread = "MainThread"
            self.emit(self.pod.stopped + self.s(0.02, 0.09), "DEBUG", "dispatch.scheduler", "Stopping scheduler...")

    def dispatch(self, name, path, func, at):
        self.thread = f"Thread-{self.rng.randint(1, 100)} (worker)"
        t0 = at
        if self.w.db_down(at):
            self.w.db_failed.append(name)
            at = self.db_failure(fullname(path, func), at)
        else:
            at = getattr(self, func)(at + self.s(0.0005, 0.003))
        if name not in UNTIMED:
            self.timer(at, fullname(path, func), (at - t0).total_seconds() + 1e-5)

    def db_failure(self, name, at):
        """The organization query in _execute_task_in_project_context fails before any project is touched."""
        kind = self.w.db_error_kind(at, self.db_failures)
        self.db_failures += 1
        at += self.s(0.002, 0.009) if kind != "closed" else self.s(0.01, 0.04)
        self.emit(at, "ERROR", "dispatch.decorators", f"Error trying to execute task: {name}")
        psycopg = p2.PG_ERRORS[kind]
        if kind == "closed":
            message = f"(psycopg2.OperationalError) {psycopg}\n{p2.ORG_SQL}\n{p2.SQLA_BACKGROUND}"
            cause = p2.lib(p2.SQLA_EXECUTE)
            chain = p2.lib(p2.SQLA_ORM_ITER) + p2.lib(p2.SQLA_ORM_EXECUTE) + p2.lib(p2.SQLA_EXECUTE)
        else:
            message = f"(psycopg2.OperationalError) {psycopg}\n{p2.SQLA_BACKGROUND}"
            cause = p2.lib(p2.SQLA_CONNECT_HEAD) + p2.lib(p2.SQLA_POOL_REUSE) + p2.lib(p2.SQLA_CONNECT_TAIL)
            chain = p2.lib(p2.SQLA_ORM_ITER) + p2.lib(p2.SQLA_ORM_CONNECT) + p2.lib(p2.SQLA_CONNECT_WRAP) + cause
        loop_frame = self.src.frame("decorators.py", "_execute_task_in_project_context", "for organization in organization_service.get_all(")
        text = "\n".join([message, "Traceback (most recent call last):", *cause, f"psycopg2.OperationalError: {psycopg}", "",
                          "The above exception was the direct cause of the following exception:", "",
                          "Traceback (most recent call last):", *loop_frame, *chain, f"sqlalchemy.exc.OperationalError: {message}"])
        self.emit(at + self.s(0.0001, 0.0004), "ERROR", "dispatch.decorators", text)
        return at + self.s(0.0003, 0.001)

    def per_project(self, at, level, path, template):
        for project in self.projects(at):
            at += self.s(0.004, 0.015)
            self.emit(at, level, module(path), template.format(p=project.name))
        return at

    # -- case costs (case_cost/scheduled.py)

    def calculate_cases_response_cost(self, at):
        for project in self.projects(at):
            at += self.s(0.01, 0.04)
            for case in self.w.cases:
                if case.project is not project or case.created > at:
                    continue
                status, stamps = case.state(at)
                if status not in ("New", "Triage", "Stable"):
                    continue
                at += self.s(0.004, 0.012)
                row = self.w.costs.get(case.id)
                if row is None:  # get_or_create_case_response_cost_by_model_type()
                    row = self.w.costs[case.id] = CostRow(at)
                if status == "Stable" and "stable" in stamps and row.updated_at > stamps["stable"]:
                    continue  # cost already updated after it went stable
                at += self.s(0.006, 0.02)
                self.emit(at, "DEBUG", "dispatch.case_cost.service", "No case cost model found. Skipping this case.")
                at += self.s(0.004, 0.02)
                if project.hourly_rate is None:
                    self.type_error(at)
                    at += self.s(0.001, 0.004)
                    continue
                amount = classic_cost(case, at, self.src.latest_cut_off)
                if amount != row.amount:
                    at += self.s(0.003, 0.012)
                    row.set(at, amount)
        return at

    def type_error(self, at):
        """get_hourly_rate() on a project whose annual_employee_cost is NULL; the job logs it and moves on."""
        f = self.src.frame
        frames = (f("case_cost/scheduled.py", "calculate_cases_response_cost", "results = update_case_response_cost(case, db_session)",
                    hl="update_case_response_cost(case, db_session)")
                  + f("case_cost/service.py", "update_case_response_cost", "costs = calculate_case_response_cost(case=case, db_session=db_session)",
                      after="def update_case_response_cost(", hl="calculate_case_response_cost(case=case, db_session=db_session)")
                  + f("case_cost/service.py", "calculate_case_response_cost", "new_amount = calculate_case_response_cost_new(case=case, db_session=db_session)",
                      after="def calculate_case_response_cost(", hl="calculate_case_response_cost_new(case=case, db_session=db_session)")
                  + f("case_cost/service.py", "calculate_case_response_cost_new", "hourly_rate = get_hourly_rate(case.project)",
                      after="def calculate_case_response_cost_new(", hl="get_hourly_rate(case.project)")
                  + f("case_cost/service.py", "get_hourly_rate", "return math.ceil(project.annual_employee_cost / project.business_year_hours)",
                      after="def get_hourly_rate(", hl="project.annual_employee_cost / project.business_year_hours", binop=(29, 1)))
        message = "unsupported operand type(s) for /: 'NoneType' and 'int'"
        self.emit(at, "ERROR", "dispatch.case_cost.scheduled",
                  "\n".join([message, "Traceback (most recent call last):", *frames, f"TypeError: {message}"]))
        self.w.type_errors.append(at)

    # -- incidents

    def incidents(self, project, at, *statuses):
        return [i for i in self.w.incidents if i.project is project and i.status(at) in statuses]

    def calculate_incidents_response_cost(self, at):
        for project in self.projects(at):
            at += self.s(0.006, 0.02)
            for inc in self.incidents(project, at, "Active", "Stable"):
                at += self.s(0.01, 0.04)
                self.emit(at, "DEBUG", "dispatch.incident_cost.service", "No incident cost model found. Defaulting to classic incident cost model.")
                at += self.s(0.004, 0.015)
        return at + self.s(0.002, 0.008)

    def incident_sync_members(self, at):
        for project in self.projects(at):
            at += self.s(0.005, 0.02)
            if not project.slack:
                self.emit(at, "WARNING", "dispatch.incident.scheduled", "No conversation plugin is active.")
                continue
            for _ in self.incidents(project, at, "Active", "Stable"):
                at = self.plugin(at, SLACK + "get_all_member_emails", 0.35, 1.6)
        return at + self.s(0.003, 0.01)

    def incident_report_reminders(self, at):
        for project in self.projects(at):
            at += self.s(0.005, 0.02)
            for inc in self.incidents(project, at, "Active"):
                hours = int((at - inc.created).total_seconds() // 3600)
                if hours >= 6 and hours % 6 == 0:  # tactical reports are due every 6 hours at this priority
                    at = self.plugin(at + self.s(0.002, 0.008), SLACK + "get_command_name", 1.4e-06, 5.2e-06)
                    at = self.plugin(at, SLACK + "send_direct", 0.25, 0.9)
                    self.emit(at, "DEBUG", "dispatch.report.messaging", f"Incident report reminder sent to {inc.commander}.")
        return at

    def incident_report_delayed_reminders(self, at):
        return at + self.s(0.004, 0.03)

    def incident_auto_tagger(self, at):
        return self.per_project(at, "WARNING", "incident/scheduled.py",
                                "Incident tags not updated. No storage plugin enabled. Project: {p}. Organization: default")

    def incident_report_daily(self, at):
        at += self.s(0.01, 0.04)
        day = timedelta(hours=24)
        listed = [i for i in self.w.incidents if i.status(at) == "Active" or (i.status(at) == "Stable" and at - i.stable_at < day)
                  or (i.status(at) == "Closed" and at - i.closed_at < day)]
        if listed:
            at = self.plugin(at + self.s(0.02, 0.08), SLACK + "send", 0.4, 1.3)
        return at + self.s(0.002, 0.01)

    def incident_close_reminder(self, at):
        for project in self.projects(at):
            at += self.s(0.005, 0.02)
            for inc in self.incidents(project, at, "Stable"):
                if (at - inc.stable_at).days // 7 >= 1 and at.isoweekday() == 1:
                    at = self.plugin(at + self.s(0.002, 0.006), SLACK + "get_command_name", 1.4e-06, 5.2e-06)
                    at = self.plugin(at, SLACK + "send_direct", 0.25, 0.9)
                    self.emit(at, "DEBUG", "dispatch.incident.messaging", f"Incident close reminder sent to {inc.commander}.")
        return at + self.s(0.002, 0.008)

    def incident_report_weekly(self, at):
        at += self.s(0.004, 0.012)  # only the security project sends weekly reports
        self.emit(at, "WARNING", "dispatch.incident.scheduled", "Incident weekly reports not sent. No AI plugin enabled.")
        return at + self.s(0.002, 0.008)

    # -- case reminders (case/scheduled.py; the weekly ones never fire: _is_reminder_day() is never true)

    def case_close_reminder(self, at):
        return at + self.s(0.01, 0.05)

    def case_stable_reminder(self, at):
        return at + self.s(0.01, 0.04)

    def case_triage_reminder(self, at):
        for project in self.projects(at):
            at += self.s(0.008, 0.035)
            for case in self.w.cases:
                if case.project is not project or case.created > at or case.status(at) != "New" or (at - case.created).days < 1:
                    continue
                at += self.s(0.003, 0.01)
                if not project.slack:
                    self.emit(at, "WARNING", "dispatch.case.messaging", "Case triage reminder message not sent. No conversation plugin enabled.")
                    continue
                if case.assignee is None:
                    self.emit(at, "WARNING", "dispatch.case.messaging", f"Case triage reminder message not sent. No assignee for {case.name}.")
                    continue
                at = self.plugin(at, SLACK + "send_direct", 0.25, 0.9)
                self.emit(at, "DEBUG", "dispatch.case.messaging", f"Case triage reminder sent to {case.assignee}.")
        return at

    # -- the rest

    def sync_sources(self, at):
        return self.per_project(at, "DEBUG", "data/source/scheduled.py",
                                "Data sources not synced. No source plugin enabled. Project: {p}. Organization: default")

    def sync_tags(self, at):
        return self.per_project(at, "WARNING", "tag/scheduled.py",
                                "Tags not synced using external sources. No tag plugin enabled. Project: {p}. Organization: default")

    def sync_terms(self, at):
        return self.per_project(at, "WARNING", "term/scheduled.py",
                                "Skipping syncing terms. No term plugin enabled. Project: {p}. Organization: default")

    def create_incident_tasks_reminders(self, at):
        return self.per_project(at, "DEBUG", "task/scheduled.py", "Overdue tasks in {p} project that need reminders: 0")

    def sync_document_terms(self, at):
        return self.per_project(at, "WARNING", "document/scheduled.py",
                                "Document terms not synced. No storage plugin enabled. Project: {p}. Organization: default")

    def sync_incident_tasks_daily(self, at):
        return self.per_project(at, "WARNING", "task/scheduled.py",
                                "Daily incident tasks sync skipped. No task plugin enabled. Project: {p}. Organization: default")

    def build_tag_models(self, at):
        for project in self.projects(at):
            at += self.s(0.01, 0.04)
            self.emit(at, "DEBUG", "dispatch.tag.scheduled", f"Building the incident tag recommendation models for project {project.name}...")
            at += self.s(0.8, 2.6) if project is DEFAULT else self.s(0.02, 0.08)
            self.emit(at, "DEBUG", "dispatch.tag.scheduled", "Successfully built the incident tag recommendation models.")
        return at

    def create_evergreen_reminders(self, at):
        at += self.s(0.04, 0.12)
        self.emit(at, "WARNING", "dispatch.evergreen.scheduled",
                  "Evergreen reminder not sent. No email plugin enabled. Project: {project.name}. Organization: {project.organization.name}")
        return at + self.s(0.002, 0.008)

    def feedback_report_daily(self, at):
        at += self.s(0.01, 0.03)
        for _ in range(random.Random(at.date().toordinal()).choice([0, 0, 1, 1, 2])):
            at += self.s(0.003, 0.01)
            self.emit(at, "WARNING", "dispatch.feedback.incident.messaging", "Case feedback daily report not sent. Email plugin is not enabled.")
        return at + self.s(0.002, 0.008)

    def oncall(self, at, passes):
        for project in self.projects(at):
            at += self.s(0.01, 0.03)
            if project is DEFAULT:  # the engineering on-call rota is in PagerDuty
                for _ in range(passes):
                    at = self.plugin(at, PD + "get_schedule_id_from_service_id", 0.2, 0.7)
                    at = self.plugin(at, PD + "did_oncall_just_go_off_shift", 0.3, 0.9)
                continue
            for _ in range(passes):
                at += self.s(0.003, 0.01)
                self.emit(at, "WARNING", "dispatch.feedback.service.scheduled",
                          f"Skipping collection of oncall shift feedback for project {project.name}. No oncall plugin enabled.")
        return at + self.s(0.002, 0.008)

    def oncall_shift_feedback_ucan(self, at):
        return self.oncall(at, 2)

    def oncall_shift_feedback_emea(self, at):
        return self.oncall(at, 1)


# --- case-cost-sync -------------------------------------------------------------------------------------

class CostSync:
    """The finance team's hourly copy of case costs into the warehouse."""

    def __init__(self, world):
        self.w, self.rng, self.log = world, world.rng, world.sync_log
        self.warehouse = {}  # case id -> classic amount as of the last sync
        self.flagged = []

    def seed(self, at):
        """What the warehouse holds from the runs before the window."""
        for case in self.w.cases:
            if case.created <= at:
                row = self.w.costs.get(case.id)
                self.warehouse[case.id] = (row.at(at) if row else None) or 0

    def emit(self, at, level, name, message):
        self.log.add(at, f"[{iso_ms(at)}] {level} {name} - {message}")

    def s(self, lo, hi):
        return timedelta(seconds=self.rng.uniform(lo, hi))

    def run(self, scheduled, started):
        version = "1.5.0" if scheduled >= SYNC_UPGRADE else "1.4.2"
        per_page = 100 if version == "1.5.0" else 50
        at = started + self.s(0.9, 1.6)
        self.emit(at, "INFO", "costsync", f"case-cost-sync {version}, run {iso_s(scheduled)}")
        at += self.s(0.05, 0.2)
        self.emit(at, "DEBUG", "urllib3.connectionpool", f"Starting new HTTPS connection (1): {DISPATCH_HOST}:443")
        # newest cases first, until a page reaches cases created more than 40 days before the run
        listed = [c for c in sorted(self.w.cases, key=lambda c: -c.id) if c.created <= at]
        cutoff = scheduled - timedelta(days=40)
        pages = []
        for i in range(0, len(listed), per_page):
            pages.append(listed[i:i + per_page])
            if pages[-1][-1].created < cutoff:
                break
        read_started = at
        for n, page in enumerate(pages, 1):
            path = f"/api/v1/{ORG}/cases?page={n}&itemsPerPage={per_page}&sortBy[]=id&descending[]=true"
            if scheduled == SYNC_TIMEOUT and n == 2:
                at += timedelta(seconds=30.0) + self.s(0.001, 0.004)
                self.emit(at, "WARNING", "urllib3.connectionpool",
                          "Retrying (Retry(total=2, connect=None, read=None, redirect=None, status=None)) after connection broken by "
                          f"'ReadTimeoutError(\"HTTPSConnectionPool(host='{DISPATCH_HOST}', port=443): Read timed out. (read timeout=30)\")': {path}")
                at += self.s(0.002, 0.01)
                self.emit(at, "DEBUG", "urllib3.connectionpool", f"Starting new HTTPS connection (2): {DISPATCH_HOST}:443")
            at += self.s(0.25, 0.6) * (len(page) / 50)
            self.emit(at, "DEBUG", "urllib3.connectionpool",
                      f'https://{DISPATCH_HOST}:443 "GET {path} HTTP/1.1" 200 {len(page) * self.rng.randint(1880, 2140)}')
        read = [c for page in pages for c in page]
        at += self.s(0.01, 0.04)
        self.emit(at, "INFO", "costsync.source", f"read {len(read)} cases from Dispatch in {len(pages)} pages ({(at - read_started).total_seconds():.2f}s)")
        at += self.s(0.05, 0.15)
        self.emit(at, "DEBUG", "costsync.warehouse", f"connected to {WAREHOUSE} as svc_case_cost_sync")
        changed, flagged = 0, []
        values = {}
        for case in sorted(read, key=lambda c: c.id):
            row = self.w.costs.get(case.id)
            amount = row.at(read_started) if row else None
            amount = 0 if amount is None else amount
            values[case.id] = amount
            old = self.warehouse.get(case.id)
            if old is None:
                at += self.s(0.0005, 0.002)
                self.emit(at, "INFO", "costsync.diff", f"case {case.id} added, classic {amount}")
                changed += 1
            elif old != amount:
                at += self.s(0.0005, 0.002)
                self.emit(at, "INFO", "costsync.diff", f"case {case.id} classic {old} -> {amount}")
                changed += 1
                if old > 0 and amount > old * 1.5 and amount - old > 500:
                    flagged.append((case, old, amount))
        for case, old, amount in flagged:
            at += self.s(0.0005, 0.002)
            status = case.status(read_started)
            self.emit(at, "WARNING", "costsync.checks",
                      f"case {case.id} ({case.name}, {status}): classic cost {old} -> {amount} "
                      f"(+{round(100 * (amount - old) / old)}%) since the last sync, flagged for review")
            self.flagged.append((at, case, old, amount, status))
        at += self.s(0.08, 0.3)
        self.emit(at, "INFO", "costsync.warehouse", f"upserted {changed} rows into finance.case_response_cost ({self.rng.uniform(0.04, 0.3):.2f}s)")
        self.warehouse.update(values)
        at += self.s(0.002, 0.01)
        took = (at - started).total_seconds()
        if version == "1.5.0":
            self.emit(at, "INFO", "costsync", f"run {iso_s(scheduled)} done in {took:.2f}s: {len(read)} read, {changed} changed, {len(flagged)} flagged")
        else:
            self.emit(at, "INFO", "costsync", f"done: {len(read)} cases, {changed} changed, {len(flagged)} flagged, {took:.2f}s")
        return at


# --- Kubernetes events ---------------------------------------------------------------------------------

class Events:
    def __init__(self, world):
        self.w, self.rng, self.log = world, world.rng, world.events_log
        self.pulled = {}  # node -> images present

    def emit(self, at, kind, reason, obj, message):
        self.log.add(at, f"{iso_s(at)} {kind} {reason} {obj}: {message}")

    def s(self, lo, hi):
        return timedelta(seconds=self.rng.uniform(lo, hi))

    def start_pod(self, at, pod, container, image, node, fail_first_pull=False):
        """Scheduled, image pulled (or already there), container created and started; returns the start time."""
        self.emit(at, "Normal", "Scheduled", f"pod/{pod}", f"Successfully assigned dispatch/{pod} to {node}")
        at += self.s(0.3, 1.2)
        present = self.pulled.setdefault(node, set())
        if image in present:
            self.emit(at, "Normal", "Pulled", f"pod/{pod}", f'Container image "{image}" already present on machine')
        else:
            if fail_first_pull:
                tag = image.rsplit(":", 1)[1]
                self.emit(at, "Normal", "Pulling", f"pod/{pod}", f'Pulling image "{image}"')
                at += self.s(1.0, 2.5)
                self.emit(at, "Warning", "Failed", f"pod/{pod}",
                          f'Failed to pull image "{image}": failed to pull and unpack image "{image}": failed to resolve reference "{image}": '
                          f"unexpected status from HEAD request to https://registry.example.com/v2/dispatch/manifests/{tag}: 502 Bad Gateway")
                self.emit(at, "Warning", "Failed", f"pod/{pod}", "Error: ErrImagePull")
                at += self.s(0.5, 1.5)
                self.emit(at, "Normal", "BackOff", f"pod/{pod}", f'Back-off pulling image "{image}"')
                self.emit(at, "Warning", "Failed", f"pod/{pod}", "Error: ImagePullBackOff")
                at += self.s(10, 20)
            self.emit(at, "Normal", "Pulling", f"pod/{pod}", f'Pulling image "{image}"')
            took = self.rng.uniform(9, 19)
            at += timedelta(seconds=took)
            size = 1187395412 if "dispatch:" in image else 93812441
            self.emit(at, "Normal", "Pulled", f"pod/{pod}",
                      f'Successfully pulled image "{image}" in {took:.3f}s ({took:.3f}s including waiting). Image size: {size} bytes.')
            present.add(image)
        self.emit(at, "Normal", "Created", f"pod/{pod}", f"Created container {container}")
        at += self.s(0.2, 0.7)
        self.emit(at, "Normal", "Started", f"pod/{pod}", f"Started container {container}")
        return at

    def cronjob(self, name, scheduled, container, image, node, keep, history, work):
        """One run of a CronJob; `work(started)` returns when the container exits."""
        job = f"{name}-{int(scheduled.timestamp() // 60)}"
        pod = f"{job}-{suffix(self.rng)}"
        at = scheduled + self.s(0.02, 0.6)
        self.emit(at, "Normal", "SuccessfulCreate", f"cronjob/{name}", f"Created job {job}")
        at += self.s(0.01, 0.08)
        self.emit(at, "Normal", "SuccessfulCreate", f"job/{job}", f"Created pod: {pod}")
        at += self.s(0.01, 0.1)
        started = self.start_pod(at, pod, container, image, node)
        at = work(started) + self.s(0.4, 1.4)
        self.emit(at, "Normal", "Completed", f"job/{job}", "Job completed")
        at += self.s(0.1, 0.9)
        self.emit(at, "Normal", "SawCompletedJob", f"cronjob/{name}", f"Saw completed job: {job}, status: Complete")
        history.append(job)
        if len(history) > keep:
            self.emit(at, "Normal", "SuccessfulDelete", f"cronjob/{name}", f"Deleted job {history.pop(0)}")

    def rollout_web(self, at, old_rs, old_pods, new_rs, image, fail_first_pull=False):
        """RollingUpdate, maxSurge 1, maxUnavailable 0: one new pod ready, then one old pod gone."""
        new_pods = []
        for i in range(len(old_pods)):
            self.emit(at, "Normal", "ScalingReplicaSet", "deployment/dispatch-web",
                      f"Scaled up replica set {new_rs} to {i + 1}" + (f" from {i}" if i else ""))
            pod = f"{new_rs}-{suffix(self.rng)}"
            at += self.s(0.01, 0.06)
            self.emit(at, "Normal", "SuccessfulCreate", f"replicaset/{new_rs}", f"Created pod: {pod}")
            at += self.s(0.01, 0.1)
            at = self.start_pod(at, pod, "web", image, NODES[i % 3], fail_first_pull=fail_first_pull and i == 0)
            new_pods.append(pod)
            at += self.s(14, 24)  # readiness: the app takes a while to import its plugins
            remaining = len(old_pods) - i - 1
            self.emit(at, "Normal", "ScalingReplicaSet", "deployment/dispatch-web",
                      f"Scaled down replica set {old_rs} to {remaining} from {remaining + 1}")
            gone = old_pods[i]
            at += self.s(0.01, 0.05)
            self.emit(at, "Normal", "Killing", f"pod/{gone}", "Stopping container web")
            self.emit(at, "Normal", "SuccessfulDelete", f"replicaset/{old_rs}", f"Deleted pod: {gone}")
            at += self.s(0.3, 1.5)
        return new_pods

    def rollout_scheduler(self, at, old_rs, old_pod, new_rs, image, node):
        """Recreate: the old scheduler stops before the new one starts, so two never run at once."""
        self.emit(at, "Normal", "ScalingReplicaSet", "deployment/dispatch-scheduler", f"Scaled down replica set {old_rs} to 0 from 1")
        self.emit(at, "Normal", "Killing", f"pod/{old_pod}", "Stopping container scheduler")
        at += self.s(0.02, 0.1)
        self.emit(at, "Normal", "SuccessfulDelete", f"replicaset/{old_rs}", f"Deleted pod: {old_pod}")
        at += self.s(24, 30)  # terminationGracePeriodSeconds lets running jobs finish
        self.emit(at, "Normal", "ScalingReplicaSet", "deployment/dispatch-scheduler", f"Scaled up replica set {new_rs} to 1")
        pod = f"{new_rs}-{suffix(self.rng)}"
        at += self.s(0.01, 0.06)
        self.emit(at, "Normal", "SuccessfulCreate", f"replicaset/{new_rs}", f"Created pod: {pod}")
        at += self.s(0.01, 0.1)
        return pod, self.start_pod(at, pod, "scheduler", image, node)

    def upgrade_job(self, at, tag, image):
        """The Argo CD PreSync hook that runs `dispatch database upgrade` before each rollout."""
        job = f"dispatch-db-upgrade-{tag}"
        pod = f"{job}-{suffix(self.rng)}"
        self.emit(at, "Normal", "SuccessfulCreate", f"job/{job}", f"Created pod: {pod}")
        at = self.start_pod(at + self.s(0.01, 0.1), pod, "upgrade", image, NODES[1])
        at += self.s(6, 11)
        self.emit(at, "Normal", "Completed", f"job/{job}", "Job completed")
        return at + self.s(1, 3)


# --- putting it together ------------------------------------------------------------------------------

class World:
    def __init__(self, rng):
        self.rng = rng
        self.cases, self.incidents, self.escalated = build_world(rng)
        self.costs = {}
        self.type_errors = []
        self.db_failed = []
        self.scheduler_log, self.sync_log, self.events_log = Log(), Log(), Log()

    @staticmethod
    def db_down(at):
        return DB_FAILOVER[0] <= at < DB_FAILOVER[1]

    @staticmethod
    def db_error_kind(at, failures_so_far):
        if at >= DB_FAILOVER[1] - timedelta(seconds=20):
            return "starting"
        return "closed" if failures_so_far == 0 else "refused"


def autoscale(world, ev, web, image_of):
    """dispatch-web goes from 3 to 4 pods on busy weekday afternoons, and back in the evening."""
    rng = world.rng
    day = START
    while day < END:
        if day.isoweekday() < 6 and rng.random() < 0.7:
            up = day + timedelta(hours=rng.uniform(13.2, 15.6))
            down = up + timedelta(hours=rng.uniform(2.5, 5))
            if not any(abs((d - up).total_seconds()) < 3 * 3600 or abs((d - down).total_seconds()) < 3600
                       for d in DEPLOYS + [NODE_DRAIN]):
                rs = web(up)
                pod = f"{rs}-{suffix(rng)}"
                ev.emit(up, "Normal", "SuccessfulRescale", "horizontalpodautoscaler/dispatch-web",
                        "New size: 4; reason: cpu resource utilization (percentage of request) above target")
                ev.emit(up, "Normal", "ScalingReplicaSet", "deployment/dispatch-web", f"Scaled up replica set {rs} to 4 from 3")
                at = up + ev.s(0.01, 0.06)
                ev.emit(at, "Normal", "SuccessfulCreate", f"replicaset/{rs}", f"Created pod: {pod}")
                ev.start_pod(at + ev.s(0.01, 0.1), pod, "web", image_of(up), nodes_at(up)[rng.randrange(3)])
                if rng.random() < 0.35:
                    t = up + timedelta(seconds=rng.uniform(4, 9))
                    ev.emit(t, "Warning", "Unhealthy", f"pod/{pod}",
                            'Readiness probe failed: Get "http://10.42.%d.%d:8000/api/v1/healthcheck": context deadline exceeded '
                            "(Client.Timeout exceeded while awaiting headers)" % (rng.randint(1, 3), rng.randint(2, 250)))
                ev.emit(down, "Normal", "SuccessfulRescale", "horizontalpodautoscaler/dispatch-web", "New size: 3; reason: All metrics below target")
                ev.emit(down, "Normal", "ScalingReplicaSet", "deployment/dispatch-web", f"Scaled down replica set {rs} to 3 from 4")
                at = down + ev.s(0.01, 0.05)
                ev.emit(at, "Normal", "Killing", f"pod/{pod}", "Stopping container web")
                ev.emit(at, "Normal", "SuccessfulDelete", f"replicaset/{rs}", f"Deleted pod: {pod}")
        day += timedelta(days=1)


def main():
    build = Path(sys.argv[1])
    rng = random.Random(20250915)
    fixture = build / "fixture.git"
    plant = json.loads((build / "plants.json").read_text())["plants"][PLANT]

    starts = [EARLIER_DEPLOY] + DEPLOYS
    shas = [deployed_commit(fixture, d) for d in starts]
    sources = [Source(fixture, sha, plant) for sha in shas]
    expected = [False] * (SHIPS_PLANT + 1) + [True] * (len(DEPLOYS) - SHIPS_PLANT)
    assert [s.has_plant for s in sources] == expected, "only the rollout of DEPLOYS[SHIPS_PLANT] on may ship the plant"
    tags = [sha[:8] for sha in shas]

    world = World(rng)
    ev = Events(world)
    for node in NODES:  # images the nodes already hold when the window opens
        ev.pulled[node] = {IMAGE.format(tags[0]), SYNC_IMAGE.format("1.4.2"), BACKUP_IMAGE}
    ev.pulled[SPARE_NODE] = {SYNC_IMAGE.format("1.5.0"), BACKUP_IMAGE}

    # deployments: replica set names per image, pods per rollout
    rs = {d: [f"dispatch-{d}-{suffix(rng, 10)}" for _ in starts] for d in ("web", "scheduler")}
    web_pods = [f"{rs['web'][0]}-{suffix(rng)}" for _ in range(3)]
    sched_pod = f"{rs['scheduler'][0]}-{suffix(rng)}"
    sched_node = NODES[2]
    sched_pods = [Pod(rng, "warm", WARM, EARLIER_DEPLOY, shas[0], sources[0])]  # builds the cost history, writes nothing
    started = EARLIER_DEPLOY + timedelta(seconds=31.4)
    for i in range(1, len(starts)):
        at = starts[i]
        tag, image = tags[i], IMAGE.format(tags[i])
        at = ev.upgrade_job(at, tag, image)
        # Argo CD applies both deployments at once; the scheduler's pod pulls on its node before web's third pod
        stop = at + timedelta(seconds=rng.uniform(4, 9))
        sched_pods.append(Pod(rng, sched_pod, started, stop, shas[i - 1], sources[i - 1]))
        sched_pod, started = ev.rollout_scheduler(stop, rs["scheduler"][i - 1], sched_pod, rs["scheduler"][i], image, sched_node)
        web_pods = ev.rollout_web(at, rs["web"][i - 1], web_pods, rs["web"][i], image, fail_first_pull=starts[i] == FIRST_PULL_FAILS)
    # the node drain: the scheduler pod is evicted and its replica set starts another one elsewhere
    at = NODE_DRAIN
    sched_pods.append(Pod(rng, sched_pod, started, at, shas[-1], sources[-1]))
    ev.emit(at, "Normal", "Killing", f"pod/{sched_pod}", "Stopping container scheduler")
    new_pod = f"{rs['scheduler'][-1]}-{suffix(rng)}"
    at += ev.s(0.05, 0.3)
    ev.emit(at, "Normal", "SuccessfulCreate", f"replicaset/{rs['scheduler'][-1]}", f"Created pod: {new_pod}")
    started = ev.start_pod(at + ev.s(0.01, 0.1), new_pod, "scheduler", IMAGE.format(tags[-1]), SPARE_NODE)
    sched_pods.append(Pod(rng, new_pod, started, END + timedelta(days=1), shas[-1], sources[-1]))
    at = NODE_DRAIN + ev.s(1.5, 4)  # then the web pod that ran there
    ev.emit(at, "Normal", "Killing", f"pod/{web_pods[2]}", "Stopping container web")
    moved = f"{rs['web'][-1]}-{suffix(rng)}"
    at += ev.s(0.05, 0.3)
    ev.emit(at, "Normal", "SuccessfulCreate", f"replicaset/{rs['web'][-1]}", f"Created pod: {moved}")
    ev.start_pod(at + ev.s(0.01, 0.1), moved, "web", IMAGE.format(tags[-1]), SPARE_NODE)

    def web_rs(at):
        return rs["web"][sum(1 for d in DEPLOYS if d <= at)]

    def image_of(at):
        return IMAGE.format(tags[sum(1 for d in DEPLOYS if d <= at)])

    autoscale(world, ev, web_rs, image_of)

    for pod in sched_pods:
        Scheduler(world, pod).run()

    sync = CostSync(world)
    sync.seed(START - timedelta(minutes=40))
    history, backups = [], []
    sync_node = lambda t: nodes_at(t)[int(t.timestamp() // 3600) % 3]
    t = START + timedelta(minutes=20)
    while t < END:
        image = SYNC_IMAGE.format("1.5.0" if t >= SYNC_UPGRADE else "1.4.2")
        ev.cronjob("case-cost-sync", t, "sync", image, sync_node(t), 3, history, lambda s, t=t: sync.run(t, s))
        if t.hour == 2:  # the nightly database backup at 02:30
            b = t + timedelta(minutes=10)
            ev.cronjob("dispatch-db-backup", b, "pg-backup", BACKUP_IMAGE, NODES[0], 3, backups,
                       lambda s: s + timedelta(seconds=rng.uniform(95, 140)))
        t += timedelta(hours=1)

    out = build / "data" / TASK
    for name, log in (("scheduler.log", world.scheduler_log), ("cost-sync.log", world.sync_log), ("events.log", world.events_log)):
        log.write(out / name)
        size = (out / name).stat().st_size
        print(f"{name}: {len(log.lines)} lines, {size / 1e6:.2f} MB")

    # what the task's answers rest on
    assert "calculate-cases-response-cost" in world.db_failed, "the failover must hit an hourly batch"
    first_flagged = min(sync.flagged, key=lambda h: h[0])
    assert all(h[0] > DEPLOYS[SHIPS_PLANT] for h in sync.flagged), "a cost was flagged before the plant shipped"
    bugged = {c.id for c in world.escalated.values()} - {world.escalated["A"].id}
    assert {h[1].id for h in sync.flagged} == bugged, "flagged cases are not the escalated/reopened ones marked stable after the deploy"
    print(f"images {tags[1:]} (running at start: {tags[0]}); the plant ships with main-{tags[1 + SHIPS_PLANT]}")
    for at, case, old, amount, status in sorted(sync.flagged, key=lambda h: h[0]):
        print(f"  flagged {iso_s(at)} case {case.id} {status}: {old} -> {amount}")
    a = world.escalated["A"]
    before, after = world.costs[a.id].history[-2:]
    print(f"  contrast: case {a.id} (escalated, marked stable {iso_s(a.timeline[3][0])} before the deploy): "
          f"{before[1]} -> {after[1]} at {iso_s(after[0])}")
    print(f"first inflated: {first_flagged[0].date()} (case {first_flagged[1].id}); "
          f"TypeErrors: {len(world.type_errors)}, first {world.type_errors[0]} -> {out}")


if __name__ == "__main__":
    main()
