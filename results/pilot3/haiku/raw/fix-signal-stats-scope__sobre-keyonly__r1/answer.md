Snooze counts are now scoped to the requested signal. With a `signal_id`, `num_snoozes_active` and `num_snoozes_expired` count only that signal's snooze filters. Without one, they still count every signal's filters. The signal test suite passes (33 passed, 1 skipped).

**Cause:** In `get_signal_stats` (`src/dispatch/signal/service.py`), the snooze-filter query filtered only on the entity expression. It never looked at `signal_id`, so filters attached to other signals for the same entity were counted too. The instance counts were already correct because their query does filter on `signal_id`.

**Fix:** When `signal_id` is set, the snooze query now adds `SignalFilter.signals.any(Signal.id == signal_id)`. That uses the existing `Signal.filters` many-to-many relationship. The change is four lines.

**Test:** I added `test_get_signal_stats_snooze_counts_scoped_to_signal` to `tests/signal/test_signal_stats_service.py`. It creates two signals with snooze filters for the same entity: one signal has one active filter, the other has two active and one expired. It checks the per-signal counts (1/0 and 2/1) and the unscoped totals (3 active, 1 expired). Against the original code the test fails with `assert 3 == 1`, so it catches the bug.

I couldn't run the linter because `ruff` isn't installed in this environment, so formatting is unchecked.