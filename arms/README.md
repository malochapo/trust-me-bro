# Arms

Each arm is Claude Code plus one tool, set up exactly as its vendor documents for
Claude Code, and nothing more. `install.sh` installs every tool once at the version
pinned in `versions.json`; for every run, `run.py` calls `<arm>/setup.sh` in a fresh,
empty `HOME` and `<arm>/probe.sh` after the agent exits.

## Contract

`setup.sh` runs with `HOME` (fresh), `CLAUDE_CONFIG_DIR=$HOME/.claude`, `REPO` (the
task's checkout), `BENCH_TOOLS`, and a clean `PATH`: `<run>/bin` (a symlink to this
arm's binary only), `BENCH_EXTRA_PATH`, system dirs. It writes into `HOME` only (it
fails if `git status` in `REPO` is not clean afterwards) and leaves:

- `$CLAUDE_CONFIG_DIR/settings.json` (`{}` if the tool writes none);
- `$HOME/mcp.json`: the `mcpServers` the tool registered in `$CLAUDE_CONFIG_DIR/.claude.json`,
  passed to `claude --strict-mcp-config --mcp-config`; `{"mcpServers":{}}` if none;
- as the last stdout line, a JSON object of extra environment for the agent;
- for a daemon, its pid in `$HOME/arm.pid` (run.py stops it, process group included).

`probe.sh` prints one JSON object; `"active": false` flags the run (`probe_inactive`).
`lib.sh` holds the shared helpers.

## Versions (latest releases on 2026-10-10)

| arm | tool | version | from |
|---|---|---|---|
| native | — | — | — |
| sobre | `sobre` | 0.1.0-rc.1 | GitHub release `malochapo/sobre-ai` v0.1.0-rc.1, `sobre-x86_64-unknown-linux-musl.tar.gz` (the build without embeddings, what `install.sh` installs by default), sha256 pinned |
| rtk | `rtk` | 0.51.0 | GitHub release `rtk-ai/rtk` v0.51.0, `rtk-x86_64-unknown-linux-musl.tar.gz` (the asset rtk's `install.sh` picks on Linux x86_64), sha256 pinned. Not crates.io: `rtk` there is another project |
| lean-ctx | `lean-ctx` | 3.11.2 | GitHub release `yvgude/lean-ctx` v3.11.2, `lean-ctx-x86_64-unknown-linux-gnu.tar.gz` (what its installer picks on glibc >= 2.35), sha256 pinned |
| headroom | `headroom` | 0.40.0 | PyPI `headroom-ai[sandbox]==0.40.0`, Python 3.13, own virtualenv |

The sobre rc.1 binary prints `sobre 0.1.0` for `--version` (fixed after rc.1); the
pinned sha256 identifies the build. `install.sh` checks every checksum and every
`--version`, and skips what is already installed.

## What each arm gets

Paths below are under the run's fresh `HOME`; `<tools>` is `$BENCH_TOOLS/bin`.

### native

Nothing: `settings.json` = `{}`, no MCP server, no extra env.

### sobre — `sobre init claude`, then `sobre index build --root $REPO`

Source: README "Connect agents" and "What init writes"; `index build` is README's
"build the indexes now rather than on first search".

- MCP server `sobre` = `{"command": "<tools>/sobre"}` (15 tools).
- Hooks in `settings.json`: `PostToolUse` `.*` → `sobre hook observe`; `PostToolUse`
  `Bash` → `sobre hook compress`; `PostToolUse` `Read` → `sobre hook read-dedup`;
  `UserPromptSubmit`, `Stop`, `PreCompact`, `SessionStart`, `SessionEnd` → `sobre hook observe`.
- Skill `~/.claude/skills/sobre/SKILL.md`.
- Warm indexes (graph, BM25, code graph) for the repo in `~/.local/share/sobre`.
- No extra env. Run non-interactively, `init` asks nothing, so sobre's optional proxy
  stays off (it serves API keys only; these runs use a subscription).
- Probe: records in `~/.local/share/sobre/usage.jsonl` (sobre's usage ledger, by event
  and by surface:tool, tokens before/after), and whether the session observer wrote
  `active_transcript.json`. Active = any ledger record or the observer ran.

### rtk — `rtk init -g --auto-patch`

Source: README "Quick Start" (`rtk init -g`, "Claude Code / Copilot (default)") and
"Auto-Rewrite Hook" (`--auto-patch`: "Non-interactive (CI/CD)"). Without a terminal,
`rtk init -g` answers "N" to patching `settings.json` and installs no hook;
`--auto-patch` is the documented way to give the default answer, "y".

- Hook in `settings.json`: `PreToolUse` `Bash` → `rtk hook claude` (found on `PATH`).
- `~/.claude/RTK.md` (a short note on condensed command output) and `@RTK.md` in
  `~/.claude/CLAUDE.md`.
- `~/.config/rtk/filters.toml` (template), `~/.local/share/rtk/history.db`.
- No MCP server, no extra env. Telemetry is opt-in and stays off.
- Probe: `rtk gain --format json` and the row counts of `history.db`. Active = at
  least one command went through rtk.

### lean-ctx — `lean-ctx init --agent claude` (from `$HOME`), then `lean-ctx index build` (in `$REPO`)

Source: `docs/guides/claude-code.md` ("Setup command", "Quick Setup") and the README
agent table, which give `lean-ctx init --agent claude` for Claude Code. (The README's
generic `lean-ctx wrap claude` only registers the MCP server and a proxy redirect,
which it skips for subscription logins.) `index build` is documented in
`docs/reference/04-code-intelligence.md`. `init` runs from `$HOME`, not a git repo,
so it writes no project files (`AGENTS.md`, `LEAN-CTX.md`, `.claude/settings.local.json`);
under `--setting-sources user` Claude Code would not read them anyway.

- MCP server `lean-ctx` = `{"command": "<tools>/lean-ctx", "alwaysLoad": true, "autoApprove": [59 ctx_* tools]}`.
- `settings.json`: hooks `PreToolUse` `Bash|bash` → `lean-ctx hook rewrite`;
  `PreToolUse` `Read|Grep|Glob|…` → `lean-ctx hook redirect`; `PostToolUse` `.*` →
  `lean-ctx hook observe`; `PostToolUse` `Read` → `lean-ctx hook read-dedup`;
  `SessionStart`, `UserPromptSubmit`, `Stop`, `PreCompact`, `SessionEnd` → `lean-ctx hook observe`.
  `permissions.allow`: the 59 `mcp__lean-ctx__*` tools; **`permissions.deny`: `Grep`, `Glob`**
  ("Replace mode", lean-ctx's default for Claude Code); a `statusLine`.
- `~/.claude/CLAUDE.md`: a lean-ctx block telling the agent to prefer `ctx_*` tools.
  Skill `~/.claude/skills/lean-ctx/`, hook scripts in `~/.claude/hooks/`.
- Warm indexes (graph, BM25, code graph) for the repo in `~/.local/share/lean-ctx`.
- No extra env. lean-ctx's product telemetry is on by default and left on.
- Probe: `lean-ctx stats json` (commands and tokens) and its session observer.
  Active = any command counted or the observer ran.

### headroom — `headroom proxy --port <free port>` + `ANTHROPIC_BASE_URL`

Source: docs `quickstart.mdx` ("Alternative: proxy mode": `headroom proxy --port 8787`,
`ANTHROPIC_BASE_URL=http://localhost:8787 claude`) and `proxy.mdx`.

**Proxy mode, not `headroom wrap claude`**: `wrap` also installs and registers the
Serena MCP server (a second, independent code-navigation tool), which would confound
what this arm measures. The proxy runs with every default: mode `cache`, savings
profile `coding`, CCR on, rate limit on, anonymous beacon on.

- Extra env: `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>` and `ENABLE_TOOL_SEARCH=true`.
  Claude Code turns tool search off for a custom base URL; headroom's docs
  (`troubleshooting.mdx`, "Claude Code context window is larger through the proxy")
  tell proxy users who launch `claude` themselves to set it, and `wrap` sets it too.
  Without it this arm would load every tool schema up front, unlike native.
- Nothing in Claude Code's config: `settings.json` = `{}`, no MCP server.
- Daemon: the proxy, pid in `$HOME/arm.pid`, log in `$HOME/headroom-proxy.log` and
  `~/.headroom/logs/`. It talks to `api.anthropic.com` directly (no proxy env).
- Warm caches from `install.sh`: the Kompress ONNX model (Hugging Face
  `chopratejas/kompress-v2-base`) is linked as `~/.cache/huggingface`; tiktoken
  vocabularies via `TIKTOKEN_CACHE_DIR` when they could be downloaded.
- Install: `headroom-ai[sandbox]`, with Python 3.13 as the docs recommend.
  - **Why not `[all]`**, the README's main install: it needs PyTorch with CUDA, several
    GB, and the build machine had about 2.7 GB of disk free.
  - **Why `[sandbox]`**: it is headroom's documented torch-free bundle
    (`installation.mdx`: "Torch-free proxy bundle for constrained environments";
    pyproject: `[all]` minus torch). It holds proxy, code, relevance, reports, otel,
    html, mcp and spreadsheet. Kompress still runs locally through the ONNX path that
    comes with `[proxy]`.
  - **Why not just `[proxy]`**: it lacks `code` (tree-sitter), so headroom's
    code-aware compression would be off on tasks that read a lot of Python.
  - **What `[all]` adds that this arm leaves out**: `ml` (the PyTorch Kompress
    backend; the ONNX backend is used instead), `memory`, `image`, `voice` and `evals`.
    Memory is off in the proxy by default. The others (image OCR, voice, eval
    harness) play no part in a Claude Code coding session.
- Checked on the installed proxy:
  - the startup log says `Code-Aware: ENABLED (AST-based compression)`; with
    `[proxy]` it said `LAZY`, and tree-sitter was missing;
  - `/health` reports Kompress `ready`, backend `onnx`, about 6 s after start.
    `setup.sh` waits for that, so the agent starts with Kompress loaded.
  - headroom's `CodeAwareCompressor` compresses `src/dispatch/signal/service.py`
    9,069 → 3,699 tokens.
  - With the default `coding` profile, the proxy leaves file reads uncompressed:
    `/v1/compress` on a `cat` of that file routed it `read_protected` and saved
    0 tokens. That is headroom's default behaviour, kept as is.
- Probe: the running proxy's `/stats` (requests, requests compressed, tokens removed),
  Kompress's state from `/health` and the `Code-Aware` line of the startup log, read
  before the proxy stops. Active = it forwarded at least one request.

## Known limits

- headroom with a subscription token: Claude Code sends the OAuth token to the custom
  base URL and headroom forwards it (its docs say tool search works through the proxy
  "with subscription and API-key auth"), but this was not verified here (no token).
  A run that fails to authenticate ends as `invalid` (API error).
- In the build container, `openaipublic.blob.core.windows.net` (tiktoken) and the
  Hugging Face xet hosts are blocked; `install.sh` fetches Kompress over plain HTTPS
  (`HF_HUB_DISABLE_XET=1`) and headroom falls back to estimated token counts without
  tiktoken. On a machine with open egress, re-run `install.sh` to cache tiktoken.
- lean-ctx's `init` denies native Grep and Glob. Claude Code's deny rules "block in
  every mode, including `bypassPermissions`" (docs, permission modes), so this arm
  cannot call Grep or Glob. That is lean-ctx's default for Claude Code, kept as is.
