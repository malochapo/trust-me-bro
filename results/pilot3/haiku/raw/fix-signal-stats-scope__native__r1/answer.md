Fixed: `GET /signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. The unscoped `GET /signals/stats` still counts every signal's filters.

**Cause:** In `get_signal_stats` (`src/dispatch/signal/service.py`), the snooze-filter query filtered by entity but never used `signal_id`. Snooze filters are linked to signals through `assoc_signal_filters`, and that link was never checked.

**Fix:** When `signal_id` is given, the snooze query now adds `SignalFilter.signals.any(Signal.id == signal_id)`, which uses the existing `signals` relationship. The instance counts are untouched.

**Test:** Added `test_get_signal_stats_snooze_counts_scoped_to_signal_id` to `tests/signal/test_signal_stats_service.py`. It creates two signals for the same entity, one with an active snooze filter and one with an expired one. It checks that the unscoped call sees 1 active and 1 expired, and that each signal ID sees only its own filter.

**Verification:**
- With the fix, `python -m pytest tests/signal/test_signal_stats_service.py` passes 7/7.
- With the fix temporarily reverted, the new test fails (1 failed, 6 passed), so it does catch the bug.
- `python -m pytest tests/signal` gives 33 passed, 1 skipped.

I did not run the full test suite.