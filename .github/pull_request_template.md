## What this changes

<!-- An arm, a task, the harness, a report... and why. -->

## Checklist

- [ ] `python3 -m unittest discover -s harness/tests -t harness/tests` passes.
- [ ] No API key or other secret in the diff, transcripts included.
- [ ] For a new or changed arm: it follows the tool's documented setup for Claude Code (link: ), its version is pinned in `arms/versions.json`, and `harness/tests/test_arms.py` covers it.
- [ ] For a change to the protocol, a task or a grader: `PROTOCOL.md`'s changelog says what changed and why.
