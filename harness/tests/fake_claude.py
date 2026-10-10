#!/usr/bin/env python3
"""A stand-in for `claude` in the harness tests.

Two options of its own, stripped before anything else (tests put them in a wrapper):
  --record-to FILE   write {"argv", "env", "cwd", "stdin"} there
  --scenario NAME    ok (default), mcp_failed, api_error, wrong_model, sleep

`--version` prints a version containing "stub", which tells run.py that no token is needed.
With `--output-format stream-json` it prints a transcript shaped like Claude Code's
(system/init, assistant messages whose usage repeats per message id, tool_use and
tool_result blocks, a subagent message, a result event with modelUsage), and edits the
repo in its cwd. With `--output-format json --json-schema ...` it answers like the judge.
"""

import json
import os
import signal
import sys
import time
from pathlib import Path

VERSION = "2.1.296 (Claude Code stub)"
SESSION = "00000000-0000-4000-8000-000000000001"

# Usage per API response. The run's usage.json must come out of these numbers.
U1 = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 1000,
      "cache_creation_input_tokens": 3000,
      "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 3000},
      "service_tier": "standard"}
U_SUB = {"input_tokens": 50, "output_tokens": 2, "cache_read_input_tokens": 0,
         "cache_creation_input_tokens": 200,
         "cache_creation": {"ephemeral_5m_input_tokens": 200, "ephemeral_1h_input_tokens": 0}}
U2 = {"input_tokens": 4, "output_tokens": 1, "cache_read_input_tokens": 4000,
      "cache_creation_input_tokens": 1500,
      "cache_creation": {"ephemeral_5m_input_tokens": 500, "ephemeral_1h_input_tokens": 1000}}
SUBAGENT_MODEL = "claude-haiku-5-5"
TOOLS = ["Agent", "Bash", "Edit", "Glob", "Grep", "Read", "TodoWrite", "Write"]


def take(argv, flag):
    if flag in argv:
        i = argv.index(flag)
        value = argv[i + 1]
        del argv[i:i + 2]
        return value
    return None


def opt(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def emit(event):
    print(json.dumps(event), flush=True)


def assistant(msg_id, model, content, usage, parent=None):
    return {"type": "assistant", "session_id": SESSION, "parent_tool_use_id": parent,
            "uuid": f"u-{msg_id}-{content[0]['type']}",
            "message": {"id": msg_id, "type": "message", "role": "assistant", "model": model,
                        "content": content, "stop_reason": None, "usage": usage}}


def tool_results(blocks, parent=None):
    return {"type": "user", "session_id": SESSION, "parent_tool_use_id": parent,
            "message": {"role": "user", "content": blocks}}


def mcp_servers(argv, scenario):
    path = opt(argv, "--mcp-config")
    servers = json.loads(Path(path).read_text()).get("mcpServers", {}) if path else {}
    statuses = []
    for i, name in enumerate(servers):
        status = "failed" if scenario == "mcp_failed" and i == 0 else "connected"
        statuses.append({"name": name, "status": status})
    return statuses, [f"mcp__{s['name']}__do_thing" for s in statuses]


def edit_repo():
    """What an agent's edits look like to the harness: one tracked change, one new file."""
    readme = Path("README.md")
    if readme.exists():
        readme.write_text(readme.read_text() + "edited by the agent\n")
    Path("NOTES.txt").write_text("new file from the agent\n")


def stream(argv, scenario):
    model = opt(argv, "--model", "claude-sonnet-5-5")
    servers, mcp_tools = mcp_servers(argv, scenario)
    emit({"type": "system", "subtype": "init", "session_id": SESSION, "uuid": "init-1",
          "cwd": os.getcwd(), "model": "claude-opus-5-5" if scenario == "wrong_model" else model,
          "permissionMode": opt(argv, "--permission-mode", "default"), "apiKeySource": "none",
          "claude_code_version": "2.1.296", "tools": TOOLS + mcp_tools, "mcp_servers": servers,
          "slash_commands": [], "output_style": "default", "skills": [], "plugins": []})
    if scenario == "sleep":
        def on_sigint(*_):
            emit({"type": "result", "subtype": "error_during_execution", "is_error": True,
                  "session_id": SESSION, "num_turns": 1, "duration_ms": 1, "duration_api_ms": 0,
                  "total_cost_usd": 0, "usage": {}, "modelUsage": {}, "permission_denials": [],
                  "errors": ["interrupted"]})
            sys.exit(130)
        signal.signal(signal.SIGINT, on_sigint)
        time.sleep(600)

    # One response with two parallel tool calls: three events share message id msg_1.
    emit(assistant("msg_1", model, [{"type": "thinking", "thinking": "plan", "signature": "s"}], U1))
    emit(assistant("msg_1", model, [{"type": "tool_use", "id": "toolu_1", "name": "Bash",
                                     "input": {"command": "git log -n 1"}}], U1))
    emit(assistant("msg_1", model, [{"type": "tool_use", "id": "toolu_2", "name": "Read",
                                     "input": {"file_path": "README.md"}}], U1))
    emit(tool_results([
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "commit abc\n"},
        {"type": "tool_result", "tool_use_id": "toolu_2", "is_error": True,
         "content": [{"type": "text", "text": "x" * 100}]},
    ]))
    # A subagent: its own model, its messages carry the Agent call's id.
    no_writes = {"cache_creation_input_tokens": 0, "cache_creation": {}}
    emit(assistant("msg_0", model, [{"type": "tool_use", "id": "toolu_3", "name": "Agent",
                                     "input": {"prompt": "look around"}}], U2 | no_writes))
    emit(assistant("msg_sub", SUBAGENT_MODEL, [{"type": "tool_use", "id": "toolu_4", "name": "Grep",
                                                "input": {"pattern": "def"}}], U_SUB, parent="toolu_3"))
    emit(tool_results([{"type": "tool_result", "tool_use_id": "toolu_4", "content": "a.py:1:def f"}],
                      parent="toolu_3"))
    emit(tool_results([{"type": "tool_result", "tool_use_id": "toolu_3",
                        "content": [{"type": "text", "text": "found it"}]}]))
    edit_repo()
    answer = "The answer is 45 minutes.\nVALUE: 45 minutes\nFILE: src/dispatch/config.py\n"
    emit(assistant("msg_2", model, [{"type": "text", "text": answer}], U2))

    result = {"type": "result", "subtype": "success", "is_error": False, "session_id": SESSION,
              "duration_ms": 12345, "duration_api_ms": 10000, "num_turns": 3, "result": answer,
              "stop_reason": "end_turn", "total_cost_usd": 0.0301,
              "usage": {"input_tokens": 14, "output_tokens": 700, "cache_read_input_tokens": 5000,
                        "cache_creation_input_tokens": 4500},
              "modelUsage": {
                  model: {"inputTokens": 14, "outputTokens": 700, "cacheReadInputTokens": 5000,
                          "cacheCreationInputTokens": 4500, "webSearchRequests": 0,
                          "costUSD": 0.03, "contextWindow": 200000, "maxOutputTokens": 64000},
                  SUBAGENT_MODEL: {"inputTokens": 50, "outputTokens": 40, "cacheReadInputTokens": 0,
                                   "cacheCreationInputTokens": 200, "webSearchRequests": 0,
                                   "costUSD": 0.0001, "contextWindow": 200000, "maxOutputTokens": 64000}},
              "permission_denials": []}
    if scenario == "api_error":
        result.update(is_error=True, result="API Error: 401 authentication_failed")
    emit(result)


def judge(argv, scenario="ok"):
    # "leak": the model answers a fact task right without the code (leakage.py's case)
    result = "It is 45 minutes.\nVALUE: 45 minutes" if scenario == "leak" else ""
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "session_id": SESSION,
                      "result": result, "num_turns": 2, "total_cost_usd": 0.001,
                      "structured_output": {"score": 2, "reasons": "stub judge"}}))


def main():
    argv = sys.argv[1:]
    record_to = take(argv, "--record-to")
    scenario = take(argv, "--scenario") or "ok"
    if "--version" in argv:
        print(VERSION)
        return
    stdin = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
    if record_to:
        Path(record_to).write_text(json.dumps({"argv": argv, "env": dict(os.environ),
                                               "cwd": os.getcwd(), "stdin": stdin}))
    if opt(argv, "--output-format") == "json":
        judge(argv, scenario)
    else:
        stream(argv, scenario)


if __name__ == "__main__":
    main()
