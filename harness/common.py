"""Helpers shared by the harness scripts (stdlib only)."""

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parent.parent
ARMS_DIR = BENCH_ROOT / "arms"
DEFAULT_FIXTURE = BENCH_ROOT / "build" / "fixture.git"
DEFAULT_PLANTS = BENCH_ROOT / "build" / "plants.json"
DEFAULT_WORK = Path("/tmp/trust-me-bro-work")
ALL_ARMS = ["native", "native-told", "sobre", "sobre-dev", "sobre-dev-06", "sobre-dev-09", "sobre-dev-09b", "sobre-hooks",
            "sobre-keyonly", "sobre-rc2", "sobre-rc2-mcp", "sobre-rc2-mcp-told", "sobre-rc2-dense", "sobre-rc2-dense-told",
            "sobre-rc3-dense", "sobre-rc3-dense-told", "sobre-dev-fold2", "sobre-dev-fold3",
            "lean-ctx", "headroom", "rtk"]
# The released tools' arms. A variant of one (a development build, or the same build set up
# differently) is named "<arm>-<variant>" and bills to that arm's key unless it has its own.
BASE_ARMS = ["native", "sobre", "lean-ctx", "headroom", "rtk"]

# The agent sees only these system directories, never the harness's own PATH
# (which, inside another Claude Code session, holds that session's tooling).
SYSTEM_PATH = ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"]

# Runs and grading share one Postgres database (`dispatch-test`, hard-coded in the
# fixture's tests/conftest.py), so they take this lock and never overlap. A run's slot is
# the Postgres server it uses, BENCH_DB_PORT (default 5432), which Dispatch reads as
# DATABASE_PORT: each slot has its own lock, so runs on different servers can overlap
# (bench.py --jobs).
DB_PORT = int(os.environ.get("BENCH_DB_PORT") or 5432)
LOCK_FILE = Path(os.environ.get("BENCH_LOCK_FILE")
                 or ("/tmp/trust-me-bro.lock" if DB_PORT == 5432 else f"/tmp/trust-me-bro.{DB_PORT}.lock"))


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_env(home, path_dirs, extra=None):
    """A minimal environment built from nothing: no variable of the caller leaks in."""
    env = {
        "PATH": ":".join(str(d) for d in path_dirs),
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(Path(home) / ".claude"),
        "LANG": "C.UTF-8",
        "TERM": "dumb",
        "IS_SANDBOX": "1",
        "DISABLE_AUTOUPDATER": "1",
    }
    if DB_PORT != 5432:
        env["DATABASE_PORT"] = str(DB_PORT)
    env.update(extra or {})
    return env


def oauth_token():
    """The subscription token for the child `claude`. Stored as BENCH_CLAUDE_OAUTH_TOKEN so it
    cannot interfere with the auth of a Claude Code session the harness itself runs in;
    CLAUDE_CODE_OAUTH_TOKEN is the fallback. Children get it only as CLAUDE_CODE_OAUTH_TOKEN."""
    return os.environ.get("BENCH_CLAUDE_OAUTH_TOKEN") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")


def credentials(who):
    """Environment for the child `claude` of an arm or of the judge, and the auth kind.

    BENCH_KEY_<WHO> (e.g. BENCH_KEY_LEANCTX, BENCH_KEY_JUDGE) is an API key: one key per arm
    lets the provider's console bill each arm on its own. Without one, the subscription token
    is used. Children get them only under the names Claude Code reads.
    """
    env_name = lambda name: "BENCH_KEY_" + name.upper().replace("-", "").replace("_", "")
    key = os.environ.get(env_name(who))
    base = next((a for a in sorted(BASE_ARMS, key=len, reverse=True) if who.startswith(a + "-")), None)
    if not key and base:
        key = os.environ.get(env_name(base))
    if key:
        return {"ANTHROPIC_API_KEY": key}, "api_key"
    token = oauth_token()
    if token:
        return {"CLAUDE_CODE_OAUTH_TOKEN": token}, "oauth_token"
    return {}, None


def extra_path_dirs():
    """Directories from BENCH_EXTRA_PATH (colon separated), if set."""
    return [d for d in os.environ.get("BENCH_EXTRA_PATH", "").split(":") if d]


def resolve_bin(name):
    """Absolute path of an executable, looked up in the harness's own PATH."""
    found = shutil.which(name)
    if not found:
        raise SystemExit(f"{name}: not found in PATH")
    return str(Path(found).resolve())


def load_task(task_file):
    task_file = Path(task_file).resolve()
    task = json.loads(task_file.read_text())
    task["_file"] = str(task_file)
    task["_dir"] = str(task_file.parent)
    return task


def arm_version(arm):
    versions = read_json(ARMS_DIR / "versions.json", {})
    return versions.get("arms", {}).get(arm)


def claude_version(claude):
    """`claude --version`, run in a clean env; a stub answers with a version containing "stub"."""
    with tempfile.TemporaryDirectory() as home:
        r = subprocess.run([claude, "--version"], env=clean_env(home, SYSTEM_PATH),
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    return (r.stdout or r.stderr).strip()


def postgres_ready(host="localhost", port=None):
    """pg_isready when installed, else a plain TCP connect. Default port: this slot's."""
    port = port or DB_PORT
    if shutil.which("pg_isready"):
        r = subprocess.run(["pg_isready", "-h", host, "-p", str(port)], capture_output=True)
        return r.returncode == 0
    import socket
    try:
        socket.create_connection((host, port), timeout=3).close()
        return True
    except OSError:
        return False


def postgres_encoding_problem(host="localhost", port=None):
    """Why the server cannot hold Dispatch's test database, or None. The fixture's
    tests create it as UTF8 from template1, which a cluster initialised with the C or
    POSIX locale (SQL_ASCII) refuses. Checked with psql when it is installed."""
    port = port or DB_PORT
    if not shutil.which("psql"):
        return None
    r = subprocess.run(["psql", "-h", host, "-p", str(port), "-U", "postgres", "-d", "postgres", "-tAc",
                        "select pg_encoding_to_char(encoding) from pg_database where datname = 'template1'"],
                       capture_output=True, text=True, env={**os.environ, "PGPASSWORD": "dispatch"})
    if r.returncode != 0:
        return f"psql on port {port} failed: {(r.stderr or r.stdout).strip()[:200]}"
    encoding = r.stdout.strip()
    if encoding != "UTF8":
        return (f"template1 on port {port} is {encoding}, not UTF8: recreate the cluster with "
                "pg_createcluster --encoding UTF8 --locale C.UTF-8")
    return None


@contextlib.contextmanager
def bench_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"waiting for {LOCK_FILE} (another run or grading holds it)", flush=True)
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def build_run_venv(venv, repo, deps_venv, log):
    """The run's own virtualenv: the shared deps (via a .pth) + the run's checkout, editable.

    `python -c 'import dispatch'` in it resolves to <repo>/src, so the agent's tests and
    the grader's tests exercise the agent's code, and runs never share an install.
    """
    uv = resolve_bin("uv")
    run = lambda cmd, **kw: subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT, **kw)
    run([uv, "venv", "-q", "-p", "3.11", str(venv)])
    purelib = lambda py: subprocess.run(
        [py, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True, capture_output=True, text=True).stdout.strip()
    deps_purelib = purelib(str(Path(deps_venv) / "bin" / "python"))
    Path(purelib(str(Path(venv) / "bin" / "python")), "_bench_deps.pth").write_text(deps_purelib + "\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    env["VIRTUAL_ENV"] = str(venv)
    run([uv, "pip", "install", "-q", "--no-deps", "--no-build-isolation", "-e", str(repo)], env=env)
