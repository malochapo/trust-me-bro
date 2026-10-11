The snooze counts on `GET /signals/{signal_id}/stats` now include only the snooze filters attached to that signal. The unscoped `GET /signals/stats` still counts every signal's filters. The new test passes with the fix and fails without it.

**Cause:** `get_signal_stats` in `src/dispatch/signal/service.py` built the snooze-filter query from the entity match alone and never applied `signal_id`. The route already passed the signal id through correctly.

**Fix:** When `signal_id` is set, the snooze query now keeps only filters whose ids appear in `assoc_signal_filters` for that signal. I used a subquery rather than a join, so a filter shared by two signals is not double-counted. Unscoped calls are unchanged.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal` in `tests/signal/test_signal_stats_service.py` sets up two signals with snooze filters on the same entity, plus an expired filter on the second. It checks the scoped counts for each signal and the unscoped total. Without the fix it fails with `assert 2 == 1`.

**Verification:**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- `ruff check` and `ruff format --check` pass on both changed files.

I didn't commit anything.