"""Generates the signal worker log for the log-dedup-regression task.

Three days of `dispatch signals process` output, as a log platform exports it:
one line per record, prefixed with a UTC timestamp and the pod name. The worker
is redeployed twice; the second deploy ships the commit that broke per-filter
deduplication windows (plant p4), so after it every GuardDuty instance opens a
case of its own. Everything else is noise drawn from messages the code really
logs. Seeded, so the file is identical on every build.

Usage: python3 -I fixture/gen_logs.py <build dir>
Reads <build>/fixture.git, writes <build>/data/log-dedup-regression/signal-worker.log
"""

import random
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

START = datetime(2025, 8, 13, tzinfo=timezone.utc)
END = datetime(2025, 8, 16, tzinfo=timezone.utc)
DEPLOYS = [datetime(2025, 8, 13, 16, 22, 4, tzinfo=timezone.utc),
           datetime(2025, 8, 14, 20, 5, 12, tzinfo=timezone.utc)]
BROKEN_FROM = DEPLOYS[1]

GUARDDUTY = "GuardDuty: Unauthorized API call"
OKTA = "Okta: Impossible travel"
CROWDSTRIKE = "CrowdStrike: Malware detected"
LAMBDA = "Lambda: Function URL exposed"
WAF = "Cloudflare: WAF block spike"
CPU = "Datadog: Host CPU saturation"


def deployed_commit(fixture, when):
    """The newest commit on main at deploy time."""
    out = subprocess.run(
        ["git", "-C", str(fixture), "log", "-1", "--format=%H", f"--before={when.isoformat()}", "main"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return out[:8]


class Log:
    def __init__(self, rng):
        self.rng = rng
        self.lines = []
        self.pod = None

    def emit(self, at, text):
        self.lines.append((at, f"{at.strftime('%Y-%m-%dT%H:%M:%S.')}{at.microsecond // 1000:03d}Z {self.pod} {text}"))

    def start_pod(self, at, image):
        suffix = "".join(self.rng.choice("bcdfghjklmnpqrstvwxz2456789") for _ in range(5))
        self.pod = f"signal-worker-6d9c7b8f5-{suffix}"
        self.emit(at, f"[kubelet] Started container signal-worker (image registry.example.com/dispatch:main-{image})")
        at += timedelta(milliseconds=2400)
        self.emit(at, "/usr/local/lib/python3.11/site-packages/starlette/config.py:60: UserWarning: Config file '.env' not found.")
        self.emit(at, "  warnings.warn(f\"Config file '{env_file}' not found.\")")


def arrivals(rng, mean_gap_min, start=START, end=END):
    t = start + timedelta(minutes=rng.uniform(0, mean_gap_min))
    while t < end:
        yield t
        t += timedelta(minutes=rng.expovariate(1 / mean_gap_min))


def guardduty_bursts(rng):
    """Bursts of 4-12 instances spread over up to ~100 minutes, every few hours."""
    t = START + timedelta(minutes=40)
    while t < END:
        at = t
        for _ in range(rng.randint(4, 12)):
            yield at
            # now and then the detector fires twice within a minute
            at += timedelta(seconds=rng.randint(15, 70)) if rng.random() < 0.12 else timedelta(minutes=rng.uniform(3, 14))
        t += timedelta(hours=rng.uniform(2.5, 5.5))


def main():
    build = Path(sys.argv[1])
    rng = random.Random(20250814)
    fixture = build / "fixture.git"
    images = [deployed_commit(fixture, d) for d in DEPLOYS]

    events = []  # (time, signal)
    events += [(t, GUARDDUTY) for t in guardduty_bursts(rng)]
    events += [(t, OKTA) for t in arrivals(rng, 9)]
    events += [(t, CROWDSTRIKE) for t in arrivals(rng, 35)]
    events += [(t, LAMBDA) for t in arrivals(rng, 600)]
    events += [(t, WAF) for t in arrivals(rng, 1.1)]
    events += [(t, CPU) for t in arrivals(rng, 2.5)]
    events.sort()

    log = Log(rng)
    log.pod = "signal-worker-6d9c7b8f5-h7kqm"
    deploys = list(zip(DEPLOYS, images))
    next_case = 48211
    open_case = {}  # signal -> (case id, time of the instance that opened it)
    crowdstrike_snoozed_host = True
    db_blip = (datetime(2025, 8, 13, 3, 12, tzinfo=timezone.utc), datetime(2025, 8, 13, 3, 19, tzinfo=timezone.utc))

    for at, signal in events:
        while deploys and deploys[0][0] <= at:
            when, image = deploys.pop(0)
            log.start_pod(when, image)
        # processing lags arrival by a moment
        at += timedelta(milliseconds=rng.randint(300, 4000))
        instance = uuid.UUID(int=rng.getrandbits(128), version=4)

        if db_blip[0] <= at <= db_blip[1]:
            log.emit(at, f"ERROR:dispatch.cli:Error processing signal instance {instance}: (psycopg2.OperationalError) server closed the connection unexpectedly")
            log.emit(at, "Traceback (most recent call last):")
            log.emit(at, '  File "/usr/local/lib/python3.11/site-packages/sqlalchemy/engine/base.py", line 1964, in _exec_single_context')
            log.emit(at, "psycopg2.OperationalError: server closed the connection unexpectedly")
            continue

        # a standing snooze covers most WAF spikes; one CrowdStrike host is snoozed too
        if (signal == WAF and rng.random() < 0.93) or (
            signal == CROWDSTRIKE and crowdstrike_snoozed_host and rng.random() < 0.6
        ):
            log.emit(at, f"INFO:dispatch.signal.flows:Signal instance {instance} ({signal}) filtered: action=snooze case_id=None")
            continue

        window = {
            GUARDDUTY: timedelta(minutes=120),
            OKTA: timedelta(minutes=45),  # no filter: the default window
            CROWDSTRIKE: timedelta(minutes=30),
            LAMBDA: timedelta(minutes=30),
            WAF: timedelta(minutes=45),  # no dedup filter: the default window
            CPU: timedelta(minutes=45),  # no filter: the default window
        }[signal]
        if signal == GUARDDUTY and at >= BROKEN_FROM:
            window = timedelta(seconds=120)

        case = open_case.get(signal)
        if case and at - case[1] <= window:
            log.emit(at, f"INFO:dispatch.signal.flows:Signal instance {instance} ({signal}) filtered: action=deduplicate case_id={case[0]}")
            continue

        case_id = next_case
        next_case += rng.randint(1, 4)  # other sources open cases too
        open_case[signal] = (case_id, at)
        log.emit(at, f"INFO:dispatch.signal.flows:Signal instance {instance} ({signal}) created case {case_id}")
        after = at + timedelta(milliseconds=rng.randint(800, 2500))
        if rng.random() < 0.05:
            log.emit(after, "ERROR:dispatch.conversation.flows:Conversation not created. Plugin slack-conversation encountered an error.")
        else:
            log.emit(after, f"INFO:dispatch.case.flows:secops-oncall@example.com added to conversation (channel ID: C0{rng.randint(10**8, 10**9 - 1)})")
        if rng.random() < 0.15:
            log.emit(after + timedelta(milliseconds=200), "WARNING:dispatch.case.flows:Case assignee not paged. No plugin of type oncall enabled.")

    log.lines.sort(key=lambda line: line[0])
    out = build / "data" / "log-dedup-regression" / "signal-worker.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(text for _, text in log.lines) + "\n")
    print(f"{len(log.lines)} lines, images {images} -> {out}")


if __name__ == "__main__":
    main()
