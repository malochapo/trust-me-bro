Recap of this round:

- **Deduplication windows** (`917a0b7b`): the per-filter dedup window was read as seconds instead of minutes, so a filter set to 30 looked back 30 seconds. The fix makes `_window_start` take minutes, which matches the UI's "Window (minutes)" field and the default-window config. Existing filters need no edits. A regression test covers a prior instance 10 minutes old (deduplicated) and one 45 minutes old (not).
- **Snoozing** (`086dc910`): an expired snooze filter stopped the loop with `break`, so a valid snooze filter listed after it was never checked. The fix uses `continue`. A regression test covers an expired filter followed by a valid one on the same entity.
- **Canary signals** (`a348bbd2`): canary instances no longer go through deduplication and are excluded from the candidate matches. Snoozing still applies to them.
- **Signal tests:** `python -m pytest tests/signal` gives 35 passed, 1 skipped.
- **Not committed:** all changes are in the working tree. The window fix also changed a stale comment in `models.py` and a docstring in `service.py`.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES