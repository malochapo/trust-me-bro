#!/usr/bin/env python3
"""One benchmark run: one task, one arm, one repetition.

Clones the fixture into work/<run_id>/repo, builds the run's virtualenv, sets the arm
up in a fresh HOME (arms/<arm>/setup.sh), runs `claude -p` in an environment built from
nothing, probes the arm, and writes everything to <out>/<run_id>/:

  stream.jsonl   Claude Code's stream-json output (stdout)
  stderr.txt     its stderr
  prompt.txt     the exact prompt (every turn's, for a multi-turn task)
  answers.md     every turn's final answer, for a multi-turn task (answer.md is the last)
  answer.md      the final answer (the result event's `result`)
  changes.patch  the repo's diff against the fixture commit (agent commits included), plus
                 untracked files as new-file diffs, listed on top
  usage.json     tokens per model and class, cost, tool calls (harness/usage.py)
  probe.json     what the arm's probe.sh saw (proof the tool was live)
  setup.log      venv build and setup.sh output
  arm/           copies of the settings.json, mcp.json and CLAUDE.md the agent got
  meta.json      ids, versions, flags, timings, exit code, init summary, status

Status: ok, timeout, error, or invalid (the run did not test what it should: setup
failed, wrong model, an MCP server not connected, an API/auth error...). Invalid runs
are re-run, never scored.

Run with `python3 -I harness/run.py ...`; see harness/README.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import hashlib
import json
import re
import os
import shutil
import signal
import subprocess
import tempfile
import time

import common
import usage

TURN_SEPARATOR = "\n\n----- next turn -----\n\n"
RESERVED_ENV = {"PATH", "HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"}

# Shell commands that reach the network: the agent could fetch upstream Dispatch and diff it.
NETWORK_COMMAND = re.compile(
    r"\b(curl\b|wget\b|git\s+(clone|fetch|pull|ls-remote)|pip3?\s+(install|download)|uv\s+(pip\s+install|add)"
    r"|npm\s+(install|i)\b|npx\b)|https?://(?!localhost|127\.0\.0\.1)"
)


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--task-file", required=True)
    p.add_argument("--arm", required=True)
    p.add_argument("--rep", type=int, required=True)
    p.add_argument("--fixture", default=str(common.DEFAULT_FIXTURE), help="bare git repo")
    p.add_argument("--out", default=str(common.BENCH_ROOT / "results" / "raw"))
    p.add_argument("--work", default=str(common.DEFAULT_WORK))
    p.add_argument("--model", default="claude-sonnet-5-5")
    p.add_argument("--effort", default="medium")
    p.add_argument("--max-turns", type=int, default=80)
    p.add_argument("--max-budget-usd", type=float, default=3)
    p.add_argument("--timeout-min", type=float, default=25)
    p.add_argument("--claude-bin", default="claude")
    p.add_argument("--bench-tools", default=os.environ.get("BENCH_TOOLS", str(Path.home() / ".cache/sobre-bench/tools")))
    p.add_argument("--deps-venv", default=os.environ.get("BENCH_DEPS_VENV"),
                   help="shared virtualenv with Dispatch's dependencies (default: $BENCH_DEPS_VENV)")
    p.add_argument("--no-venv", action="store_true", help="do not build the run's virtualenv (tests)")
    p.add_argument("--no-pg-check", action="store_true", help="do not require Postgres (tests)")
    p.add_argument("--arms-dir", default=str(common.ARMS_DIR), help=argparse.SUPPRESS)
    p.add_argument("--cleanup", action="store_true", help="delete work/<run_id> afterwards")
    p.add_argument("--force", action="store_true", help="replace an existing run dir")
    return p.parse_args(argv)


def run_id_for(task_id, arm, rep):
    return f"{task_id}__{arm}__r{rep}"


def work_name(run_id):
    """The run's work dir name. Opaque on purpose: the agent sees its cwd, HOME and data
    paths, and a path naming the arm (".../qa-001__sobre__r1/repo") would tell it."""
    return "run-" + hashlib.sha256(run_id.encode()).hexdigest()[:12]


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def copy_data(task, dest):
    """The task's data dir: `data` names a path (relative to the bench root), or is true
    for tasks/<id>/data. Returns the copy's absolute path, or None."""
    spec = task.get("data")
    src = None
    if isinstance(spec, str) and spec:
        src = Path(spec) if Path(spec).is_absolute() else common.BENCH_ROOT / spec
        if not src.exists():
            src = Path(task["_dir"]) / spec
    elif spec is True or (Path(task["_dir"]) / "data").is_dir():
        src = Path(task["_dir"]) / "data"
    if src is None:
        return None
    if not src.is_dir():
        raise SystemExit(f"task data dir not found: {spec}")
    shutil.copytree(src, dest)
    return dest.resolve()


def make_toolbin(toolbin, arm, bench_tools):
    """A bin dir holding only this arm's tool, so no other arm's binary is on PATH."""
    toolbin.mkdir(parents=True)
    entry = common.arm_version(arm) or {}
    name = entry.get("binary")
    if name:
        target = Path(bench_tools) / "bin" / name
        if not target.exists():
            raise SystemExit(f"{target} missing: run arms/install.sh")
        (toolbin / name).symlink_to(target)


def run_setup(arm_dir, env, home, log):
    """arms/<arm>/setup.sh; returns (exit code, extra env dict or None, seconds)."""
    start = time.monotonic()
    r = subprocess.run([str(arm_dir / "setup.sh")], cwd=home, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=600)
    log.write(f"--- setup.sh exit {r.returncode}\n--- stdout\n{r.stdout}--- stderr\n{r.stderr}")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    extra = None
    if r.returncode == 0 and lines:
        try:
            extra = json.loads(lines[-1])
        except ValueError:
            pass
    return r.returncode, extra, round(time.monotonic() - start, 1)


def run_probe(arm_dir, env, cwd):
    try:
        r = subprocess.run([str(arm_dir / "probe.sh")], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=120)
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        return json.loads(lines[-1]) if lines else {"error": f"no output, exit {r.returncode}: {r.stderr[-500:]}"}
    except (ValueError, subprocess.TimeoutExpired) as e:
        return {"error": f"probe failed: {e}"}


def signal_group(pid, sig):
    """Signal a process group led by pid, or the process alone. False once it is gone."""
    try:
        os.killpg(pid, sig)
        return True
    except ProcessLookupError:
        pass
    except PermissionError:
        return False
    try:
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def stop_daemon(home):
    """Stop the arm's daemon (setup.sh wrote its pid to $HOME/arm.pid)."""
    pidfile = home / "arm.pid"
    if not pidfile.exists():
        return None
    pid = int(pidfile.read_text().strip())
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not signal_group(pid, sig):
            return "stopped"
        for _ in range(50):
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return "stopped"
    return "still running"


def isolation_prefix():
    """Runs that overlap (bench.py --jobs) share the machine's processes, so one agent's
    `pkill -f pytest` would reach another run's tests and its `claude`. Each turn
    therefore runs in its own PID namespace, when `unshare` can make one: the agent sees
    and signals only its own processes. A shell is the namespace's PID 1 and `claude`
    its child, so the timeout's SIGINT reaches `claude` as it would outside."""
    unshare = shutil.which("unshare")
    if not unshare or os.environ.get("BENCH_NO_ISOLATION"):
        return []
    probe = subprocess.run([unshare, "--pid", "--fork", "--mount-proc", "--kill-child", "true"],
                           capture_output=True)
    if probe.returncode != 0:
        return []
    # The shell exports PWD; unset it so the agent gets the environment run.py built.
    return [unshare, "--pid", "--fork", "--mount-proc", "--kill-child", "sh", "-c", 'unset PWD OLDPWD; "$@"', "sh"]


def run_agent(cmd, cwd, env, out_dir, timeout_s, append=False, prompt=None):
    """Runs claude in its own session; returns (exit code, timed out). The prompt goes in
    on stdin, as typed text does, so it is not in any process's argv. A later turn of a
    multi-turn run appends to the first turn's stream and stderr."""
    mode = "ab" if append else "wb"
    with open(out_dir / "stream.jsonl", mode) as so, open(out_dir / "stderr.txt", mode) as se, \
            tempfile.TemporaryFile() as si:
        si.write((prompt or "").encode())
        si.seek(0)
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=si if prompt is not None else subprocess.DEVNULL,
                                stdout=so, stderr=se, start_new_session=True)
        timed_out = False
        try:
            rc = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            # SIGINT first: Claude Code then ends the turn and still prints its result
            # event (on SIGTERM it records no result).
            for sig, grace in ((signal.SIGINT, 30), (signal.SIGTERM, 10), (signal.SIGKILL, None)):
                signal_group(proc.pid, sig)
                try:
                    rc = proc.wait(timeout=grace)
                    break
                except subprocess.TimeoutExpired:
                    continue
    # Whatever the agent left running in its session (background commands) goes too.
    if signal_group(proc.pid, signal.SIGTERM):
        time.sleep(1)
        signal_group(proc.pid, signal.SIGKILL)
    return rc, timed_out


def capture_changes(repo, base, path):
    """Diff of the worktree against the fixture's commit (so commits the agent made count
    too), then every untracked file as a new-file diff, listed at the top."""
    untracked = [p for p in git("ls-files", "--others", "--exclude-standard", "-z", cwd=repo).split("\0") if p]
    parts = []
    if untracked:
        parts.append("# untracked files (their diffs follow the tracked changes):\n")
        parts.extend(f"#   {p}\n" for p in untracked)
    parts.append(git("diff", base, "--binary", cwd=repo))
    for p in untracked:
        r = subprocess.run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", p],
                           cwd=repo, capture_output=True, text=True)
        parts.append(r.stdout)
    path.write_text("".join(parts))
    return untracked


def validate_init(init, model, expected_servers):
    """Checks the session Claude Code started; returns (reason or None, summary)."""
    if init is None:
        return "no system/init event in the stream", None
    servers = {s.get("name"): s.get("status") for s in init.get("mcp_servers") or []}
    summary = {
        "model": init.get("model"),
        "claude_code_version": init.get("claude_code_version"),
        "permissionMode": init.get("permissionMode"),
        "apiKeySource": init.get("apiKeySource"),
        "tools": init.get("tools"),
        "mcp_servers": servers,
        "mcp_server_errors": init.get("mcp_server_errors"),
        "skills": init.get("skills"),
        "plugins": init.get("plugins"),
    }
    got = init.get("model") or ""
    if got != model and not got.startswith(model):
        return f"model is {got!r}, expected {model!r}", summary
    if init.get("permissionMode") != "bypassPermissions":
        return f"permissionMode is {init.get('permissionMode')!r}", summary
    if init.get("mcp_server_errors"):
        return f"MCP config entries skipped: {init.get('mcp_server_errors')}", summary
    for name in expected_servers:
        if servers.get(name) != "connected":
            return f"MCP server {name!r} is {servers.get(name) or 'missing'}", summary
    unexpected = sorted(set(servers) - set(expected_servers))
    if unexpected:
        return f"unexpected MCP servers {unexpected}", summary
    return None, summary


def main_loop_models(events):
    return {(e.get("message") or {}).get("model") for e in events
            if e.get("type") == "assistant" and e.get("parent_tool_use_id") is None} - {None, "<synthetic>"}


def decide_status(meta, events, result, model, expected_servers):
    inits = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    reason, summary = validate_init(inits[0] if inits else None, model, expected_servers)
    meta["init"] = summary
    for later in inits[1:]:  # each resumed turn starts its own process: check its billing too
        if not reason and meta.get("auth") == "api_key" and later.get("apiKeySource") != "ANTHROPIC_API_KEY":
            reason = f"a later turn was not billed to the arm's API key (apiKeySource {later.get('apiKeySource')!r})"
    other = sorted(m for m in main_loop_models(events) if m != model and not m.startswith(model))
    if not reason and other:
        reason = f"main loop answered by {other}"
    if not reason and meta.get("auth") == "api_key" and (summary or {}).get("apiKeySource") != "ANTHROPIC_API_KEY":
        # Without this the run could be billed to credentials the machine provides, not the arm's key.
        reason = f"not billed to the arm's API key (apiKeySource {(summary or {}).get('apiKeySource')!r})"
    for r in usage.result_events(events):
        if not reason and r.get("is_error") and r.get("subtype") == "success":
            # An API failure (auth, usage limit, ...) surfaced as the result: not the agent's doing.
            reason = f"API error: {str(r.get('result'))[:300]}"
    if reason:
        return "invalid", reason
    if meta["timed_out"]:
        return "timeout", None
    if result is None or result.get("subtype") == "error_during_execution":
        return "error", None
    if meta.get("turns_completed", 1) < meta.get("turns_planned", 1):
        return "error", None  # a turn failed, so the conversation never reached its last message
    return "ok", None


def execute(args, task, run_id, out_dir, work, claude, version, creds, auth):
    arm_dir = Path(args.arms_dir) / args.arm
    repo, home, venv, toolbin = work / "repo", work / "home", work / "venv", work / "bin"
    (home / ".claude").mkdir(parents=True)
    meta = {
        "run_id": run_id, "task_id": task["id"], "task_file": task["_file"],
        "task_sha256": common.sha256_file(task["_file"]), "family": task.get("family"),
        "grader_kind": (task.get("grader") or {}).get("kind"), "arm": args.arm, "rep": args.rep,
        "model": args.model, "effort": args.effort,
        "cli_flags": {"max_turns": args.max_turns, "max_budget_usd": args.max_budget_usd,
                      "timeout_min": args.timeout_min, "no_venv": args.no_venv},
        "claude_bin": claude, "claude_version": version, "arm_tool": common.arm_version(args.arm),
        "fixture": str(Path(args.fixture).resolve()),
        "work": {"dir": str(work), "repo": str(repo), "home": str(home),
                 "venv": None if args.no_venv else str(venv)},
        "status": None, "invalid_reason": None, "flags": [], "auth": auth,
    }
    log = open(out_dir / "setup.log", "w")
    try:
        git("clone", "--quiet", args.fixture, str(repo))
        git("remote", "remove", "origin", cwd=repo)
        meta["fixture_head"] = git("rev-parse", "HEAD", cwd=repo).strip()
        data = copy_data(task, work / "data")
        meta["work"]["data"] = str(data) if data else None
        data_dir = str(data or work / "data")
        prompts = [text.replace("{DATA_DIR}", data_dir) for text in [task["prompt"], *(task.get("followups") or [])]]
        (out_dir / "prompt.txt").write_text(TURN_SEPARATOR.join(prompts))
        if not args.no_venv:
            common.build_run_venv(venv, repo, args.deps_venv, log)
        make_toolbin(toolbin, args.arm, args.bench_tools)

        base_path = [toolbin] + common.extra_path_dirs() + common.SYSTEM_PATH
        setup_env = common.clean_env(home, base_path, {"REPO": str(repo), "BENCH_TOOLS": args.bench_tools})
        rc, extra, secs = run_setup(arm_dir, setup_env, home, log)
        meta.update(setup_exit_code=rc, setup_seconds=secs, extra_env=extra)
        mcp_config = home / "mcp.json"
        if rc != 0 or extra is None or not mcp_config.exists() or not (home / ".claude/settings.json").exists():
            meta["status"], meta["invalid_reason"] = "invalid", f"setup.sh failed (exit {rc}), see setup.log"
            return meta
        if RESERVED_ENV & set(extra):
            meta["status"], meta["invalid_reason"] = "invalid", f"setup.sh may not set {sorted(RESERVED_ENV & set(extra))}"
            return meta
        expected_servers = sorted(json.loads(mcp_config.read_text()).get("mcpServers") or {})
        save_arm_config(home, out_dir / "arm")

        agent_path = ([] if args.no_venv else [venv / "bin"]) + base_path
        agent_env = common.clean_env(home, agent_path, extra)
        agent_env.update(creds)
        flags = ["--model", args.model, "--effort", args.effort,
               "--output-format", "stream-json", "--verbose",
               "--setting-sources", "user",
               "--strict-mcp-config", "--mcp-config", str(mcp_config),
               "--permission-mode", "bypassPermissions",
               "--max-turns", str(args.max_turns), "--max-budget-usd", f"{args.max_budget_usd:g}",
                 "--disallowedTools", "WebFetch", "WebSearch"]  # variadic: keep it last
        isolation = isolation_prefix()
        meta["cmd"] = [*isolation, claude, "-p", *flags, "< prompt.txt"]
        meta["isolated"] = bool(isolation)
        meta["turns_planned"], meta["turns"] = len(prompts), []
        meta["start_utc"] = common.utc_now()
        start = time.monotonic()
        deadline = start + args.timeout_min * 60  # one limit for the whole conversation
        session_id = None
        for n, text in enumerate(prompts, 1):
            # A later turn resumes the session, as a user typing their next message would.
            resume = ["--resume", session_id] if session_id else []
            rc, timed_out = run_agent([*isolation, claude, "-p", *resume, *flags], repo, agent_env, out_dir,
                                      max(1.0, deadline - time.monotonic()), append=n > 1, prompt=text)
            meta["turns"].append({"exit_code": rc, "timed_out": timed_out})
            meta["exit_code"], meta["timed_out"] = rc, timed_out
            if timed_out or rc != 0 or n == len(prompts):
                break
            session_id = (usage.init_event(usage.read_events(out_dir / "stream.jsonl")) or {}).get("session_id")
            if not session_id:
                break
        meta["turns_completed"] = sum(1 for t in meta["turns"] if t["exit_code"] == 0 and not t["timed_out"])
        meta["wall_seconds"] = round(time.monotonic() - start, 1)
        meta["end_utc"] = common.utc_now()

        probe = run_probe(arm_dir, setup_env, repo)  # before the daemon stops: headroom reads it live
        common.write_json(out_dir / "probe.json", probe)
        meta["probe_active"] = probe.get("active")
        if args.arm != "native" and probe.get("active") is not True:
            meta["flags"].append("probe_inactive")
    finally:
        meta["daemon"] = stop_daemon(home)
        log.close()

    events = usage.read_events(out_dir / "stream.jsonl")
    result = usage.result_event(events)
    (out_dir / "answer.md").write_text((result or {}).get("result") or "")
    if meta.get("turns_planned", 1) > 1:
        (out_dir / "answers.md").write_text(TURN_SEPARATOR.join(
            r.get("result") or "" for r in usage.result_events(events)))
    meta["untracked_files"] = capture_changes(repo, meta["fixture_head"], out_dir / "changes.patch")
    meta["agent_commits"] = int(git("rev-list", "--count", f"{meta['fixture_head']}..HEAD", cwd=repo))
    run_usage = usage.compute(out_dir / "stream.jsonl")
    common.write_json(out_dir / "usage.json", run_usage)
    meta["result_subtype"] = run_usage["result_subtype"]
    if network_commands(events):
        meta["flags"].append("network_command")
        meta["network_commands"] = network_commands(events)
    meta["status"], meta["invalid_reason"] = decide_status(meta, events, result, args.model, expected_servers)
    return meta


def network_commands(events):
    """Bash commands of the run that look like network access (the main loop and subagents)."""
    found = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Bash":
                command = str((block.get("input") or {}).get("command", ""))
                if NETWORK_COMMAND.search(command):
                    found.append(command[:300])
    return found


def save_arm_config(home, dest):
    dest.mkdir()
    for src in (home / ".claude/settings.json", home / "mcp.json", home / ".claude/CLAUDE.md"):
        if src.exists():
            shutil.copy(src, dest / src.name)


def main(argv=None):
    args = parse_args(argv)
    task = common.load_task(args.task_file)
    if not (Path(args.arms_dir) / args.arm / "setup.sh").exists():
        raise SystemExit(f"unknown arm {args.arm!r}: no {args.arms_dir}/{args.arm}/setup.sh")
    claude = common.resolve_bin(args.claude_bin)
    version = common.claude_version(claude)
    creds, auth = common.credentials(args.arm)
    if not auth and "stub" not in version:
        raise SystemExit(f"set BENCH_KEY_{args.arm.upper().replace('-', '')} (an API key) or "
                         "BENCH_CLAUDE_OAUTH_TOKEN (a subscription token), see harness/README.md")
    if not args.no_venv and not args.deps_venv:
        raise SystemExit("set BENCH_DEPS_VENV (or --deps-venv) to the shared dependencies virtualenv")
    if not args.no_pg_check and not common.postgres_ready():
        raise SystemExit("Postgres is not reachable on localhost:5432 (pg_isready -h localhost)")

    run_id = run_id_for(task["id"], args.arm, args.rep)
    out_dir, work = Path(args.out).resolve() / run_id, Path(args.work).resolve() / work_name(run_id)
    if out_dir.exists():
        if not args.force:
            raise SystemExit(f"{out_dir} exists (use --force to replace it)")
        shutil.rmtree(out_dir)
    with common.bench_lock():
        shutil.rmtree(work, ignore_errors=True)
        out_dir.mkdir(parents=True)
        try:
            meta = execute(args, task, run_id, out_dir, work, claude, version, creds, auth)
        except (Exception, SystemExit) as e:  # a harness failure: the run is re-run, not scored
            meta = {"run_id": run_id, "task_id": task["id"], "arm": args.arm, "rep": args.rep,
                    "status": "invalid", "invalid_reason": f"harness error: {e!r}", "flags": []}
        common.write_json(out_dir / "meta.json", meta)
    if args.cleanup:
        shutil.rmtree(work, ignore_errors=True)
    reason = f" ({meta['invalid_reason']})" if meta.get("invalid_reason") else ""
    print(f"{run_id}: {meta['status']}{reason}", flush=True)
    return 0 if meta["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
