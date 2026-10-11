The signal stats endpoint now counts only the snooze filters attached to the requested signal when a `signal_id` is given. Without one, it still counts every signal's filters. The signal test suite passes (33 passed, 1 skipped).

**Cause:** `get_signal_stats` in `src/dispatch/signal/service.py` built the snooze-filter count from `SignalFilter` alone and never used `signal_id`. The instance counts already had the right `signal_id` check, so only the snooze query was affected.

**Fix:** After the entity match, the snooze query now adds `SignalFilter.signals.any(Signal.id == signal_id)` when `signal_id` is not `None`. That uses the existing `signals` backref to the `assoc_signal_filters` table.

**Test:** I added `test_get_signal_stats_snooze_counts_scoped_to_signal_id` to `tests/signal/test_signal_stats_service.py`. It sets up two signals whose snooze filters all match the same entity: signal 1 has one active filter, and signal 2 has one active and one expired filter. It checks:
- no `signal_id` gives 2 active and 1 expired
- signal 1 gives 1 active and 0 expired
- signal 2 gives 1 active and 1 expired

Against the original code the test fails with `assert 2 == 1`, so it catches the bug.

I couldn't run a linter because `ruff` and `black` aren't installed here, so formatting of the two changed files is unchecked.