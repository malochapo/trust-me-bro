Fixed: with a `signal_id`, the snooze counts now include only the snooze filters attached to that signal. Without one, they still count every signal's filters. The signal test suite passes (33 passed, 1 skipped), and the new test fails on the original code.

**Cause:** In `get_signal_stats` (`src/dispatch/signal/service.py`), the snooze-filter query matched any `SignalFilter` whose expression referenced the entity. It never looked at `signal_id`, and the signal-to-filter link (`assoc_signal_filters`) was not used.

**Fix:** When `signal_id` is set, the query now also requires the filter's id to appear in `assoc_signal_filters` for that signal. `assoc_signal_filters` is imported into the service. The instance counts are unchanged.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal` in `tests/signal/test_signal_stats_service.py`. Two signals share one entity. Signal 1 has an active and an expired snooze filter, and signal 2 has one active filter. It checks per-signal counts and the unscoped totals (2 active, 1 expired).

Not changed: the snooze-filter query doesn't check `action == snooze`, so any filter matching the entity is counted, whatever its action. That is outside this bug, but it may be worth a follow-up.