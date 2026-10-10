"""Builders shared by the harness tests: a tiny fixture repo, tasks, a stub claude, stub arms."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Hermetic: real credentials in the caller's environment must not change what the tests
# see, nor reach a stub. Tests that need credentials set them explicitly.
for _name in [n for n in os.environ if n.startswith("BENCH_KEY_")
              or n in ("BENCH_CLAUDE_OAUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")]:
    del os.environ[_name]

TESTS = Path(__file__).resolve().parent
HARNESS = TESTS.parent
BENCH = HARNESS.parent
FAKE = TESTS / "fake_claude.py"
sys.path.insert(0, str(HARNESS))

ANSWER = "The answer is 45 minutes.\nVALUE: 45 minutes\nFILE: src/dispatch/config.py\n"


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_fixture(root):
    src = root / "src-repo"
    src.mkdir()
    git("init", "-q", "-b", "main", cwd=src)
    (src / "README.md").write_text("fixture\n")
    git("add", "-A", cwd=src)
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init", cwd=src)
    bare = root / "fixture.git"
    git("clone", "-q", "--bare", str(src), str(bare), cwd=root)
    return bare


def make_task(root, task_id="t-001", data=True, grader=None, prompt="Read {DATA_DIR}/app.log and answer."):
    d = root / "tasks" / task_id
    d.mkdir(parents=True)
    if data:
        (d / "data").mkdir()
        (d / "data" / "app.log").write_text("log line\n")
    task = {"id": task_id, "family": "code-qa", "prompt": prompt, "data": data,
            "grader": grader or {"kind": "facts", "must": [{"id": "v", "any_of": [r"VALUE:\s*45"]}], "must_not": []}}
    (d / "task.json").write_text(json.dumps(task))
    return d / "task.json"


def make_claude(root, scenario="ok", version=None):
    """An executable `claude` that runs fake_claude.py and records its argv/env/cwd/stdin."""
    record = root / f"record-{scenario}.json"
    wrapper = root / "bin" / f"claude-{scenario}"
    wrapper.parent.mkdir(exist_ok=True)
    if version:  # a binary that does not call itself a stub
        body = f"import sys\nprint({version!r}) if '--version' in sys.argv else sys.exit(0)\n"
    else:
        body = (f"import runpy, sys\nsys.argv[1:1] = ['--record-to', {str(record)!r}, '--scenario', {scenario!r}]\n"
                f"runpy.run_path({str(FAKE)!r}, run_name='__main__')\n")
    wrapper.write_text(f"#!{sys.executable} -I\n{body}")
    wrapper.chmod(0o755)
    return wrapper, record


STUB_SETUP = """#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
echo '{"mcpServers": {"stubsrv": {"command": "/bin/true"}}}' > "$CLAUDE_CONFIG_DIR/.claude.json"
setsid sleep 300 </dev/null >/dev/null 2>&1 &
echo $! > "$HOME/arm.pid"
echo "some chatter on stdout"
finish_setup '{"STUB_EXTRA": "1"}'
"""


def make_arms(root):
    """An arms dir with the real native arm and a stub arm that registers one MCP server,
    starts a daemon and asks for one extra env var."""
    arms = root / "arms"
    shutil.copytree(BENCH / "arms" / "native", arms / "native")
    shutil.copy(BENCH / "arms" / "lib.sh", arms / "lib.sh")
    (arms / "stubarm").mkdir()
    (arms / "stubarm" / "setup.sh").write_text(STUB_SETUP)
    (arms / "stubarm" / "probe.sh").write_text("#!/usr/bin/env bash\necho '{\"active\": true, \"calls\": 1}'\n")
    for f in (arms / "stubarm").iterdir():
        f.chmod(0o755)
    return arms


def run_harness(script, args, env):
    return subprocess.run([sys.executable, "-I", str(HARNESS / script), *map(str, args)],
                          env=env, capture_output=True, text=True, timeout=300)
