Snooze counts from `GET /signals/{signal_id}/stats` now include only the snooze filters attached to that signal. The unscoped `/signals/stats` path still counts every signal's filters. The signal test suite passes (33 passed, 1 skipped), and the new test fails on the old code.

**Cause:** `get_signal_stats` in `src/dispatch/signal/service.py` counted snooze filters by matching the entity alone. The `signal_id` argument only scoped the instance counts, never the filter counts.

**Fix:** When `signal_id` is set, the filter query now also requires `SignalFilter.id` to be in `assoc_signal_filters` for that signal. I also added the `assoc_signal_filters` import to that file.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal_id` in `tests/signal/test_signal_stats_service.py` puts two signals on the same entity, with one active and one expired snooze filter on the first and one active on the second. It checks the unscoped totals (2 active, 1 expired) and the per-signal totals (1/1 and 1/0). Against the original code it fails with `assert 2 == 1`.

I didn't run a formatter because neither `ruff` nor `black` is installed here.