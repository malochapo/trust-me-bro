# Contributing

Three kinds of contribution help most:
- telling us that a tool's arm is set up wrong;
- adding an arm for a tool that is not measured yet;
- reproducing a pilot.

## Your tool's arm is set up wrong

Each arm is meant to set its tool up the way the tool's own README tells Claude Code users to, and nothing more. If an arm does something else, the benchmark has a bug. Open an issue with the "Arm setup is wrong" template, and link the part of your documentation the arm does not follow.

Answering the results is welcome too. Use Discussions, or an issue if you think a number is wrong.

## Add an arm

An arm is a directory `arms/<name>/`. [arms/README.md](arms/README.md) has the full contract; in short:

1. **`setup.sh`** runs in a fresh, empty `HOME`.
   - It installs and configures the tool as its README documents for Claude Code: hooks, MCP server, `CLAUDE.md`, proxy.
   - It writes only into `HOME`.
   - Its last line of output is a JSON object of extra environment for the agent (`{}` if none).
2. **`probe.sh`** runs after the agent exits. It prints a JSON object whose `active` field says whether the tool did anything during the run: a hook fired, the proxy saw a request, a tool was called.
3. **Install and registration:**
   - add the tool's pinned version to `arms/versions.json`. `arms/install.sh` installs a GitHub release (URL and sha256) or a PyPI package from that entry alone; another source needs a case in `install.sh`;
   - add the arm to `ALL_ARMS` and `BASE_ARMS` in `harness/common.py`.
4. **A test** in `harness/tests/test_arms.py`. It sets the arm up in a temporary home and checks what `setup.sh` left there, like the existing ones. It skips itself when the tool is not installed.

Each arm bills to its own API key, `BENCH_KEY_<NAME>` (for `my-tool`, `BENCH_KEY_MYTOOL`), so the provider's console shows each arm's spend on its own.

Results are not part of an arm's pull request. Runs are paid, and a pilot runs every arm interleaved under the same protocol ([PROTOCOL.md](PROTOCOL.md)). A new arm joins the next pilot.

## Reproduce a pilot

Each `docs/pilot-<n>.md` gives the exact commands, and [docs/RUNBOOK.md](docs/RUNBOOK.md) the machine setup. If your numbers differ from ours, open an issue with your `results/` directory or a link to it.

## Code

- **Language:** Python 3.11, standard library only.
- **Running:** every script runs with `python3 -I`.
- **Tests:** `python3 -m unittest discover -s harness/tests -t harness/tests`. They need no API key, and CI runs them on every pull request.
- **Secrets:** never commit an API key. [SECURITY.md](SECURITY.md) says what to do if one ends up in a commit or a transcript.
