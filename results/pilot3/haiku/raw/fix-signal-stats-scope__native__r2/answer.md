Snooze counts from `GET /signals/{signal_id}/stats` now include only the snooze filters attached to that signal. The unscoped `GET /signals/stats` path is unchanged and still counts every signal's filters.

**Cause:** `get_signal_stats` in `src/dispatch/signal/service.py` applied `signal_id` only to the signal-instance query. The snooze-filter query never looked at `signal_id`, so it counted every filter whose expression matched the entity.

**Fix:** when `signal_id` is set, the snooze-filter query now also requires the filter to be linked to that signal through `assoc_signal_filters`. I added that table to the existing `.models` import.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal` in `tests/signal/test_signal_stats_service.py` puts two signals on the same entity, each with its own snooze filters. It checks the unscoped totals and the per-signal counts for both. Without the fix it fails with `assert 2 == 1`; with it, it passes.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped. I didn't run the full suite.

I didn't change the frontend or the `num_days` handling. I also didn't commit.