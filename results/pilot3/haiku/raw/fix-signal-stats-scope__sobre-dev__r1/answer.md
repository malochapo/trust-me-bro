The snooze counts from `GET /signals/{signal_id}/stats` now only include snooze filters attached to that signal. The unscoped `/signals/stats` path is unchanged. The new regression test fails without the fix and passes with it, and the full `tests/signal` suite passes (33 passed, 1 skipped).

**Root cause:** `get_signal_stats` in `src/dispatch/signal/service.py` counts snooze filters with a query over `SignalFilter` that matches the entity in the filter expression. It never looked at `signal_id`. The instance query does filter on `signal_id`, which is why the instance counts were already right.

**Fix:** When `signal_id` is given, the snooze-filter query now also requires the filter to be in `assoc_signal_filters` for that signal. I added `assoc_signal_filters` to the `.models` import in the same file.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal_id` in `tests/signal/test_signal_stats_service.py`. Two signals share one entity, each with its own active snooze filter. It checks that the unscoped call counts 2, and each per-signal call counts 1.

Things I noticed but did not change:
- The snooze-filter query doesn't check `action == snooze`, so a non-snooze filter (e.g. `deduplicate`) matching the entity is also counted. The bug report didn't mention this, so I left it alone. It's a one-line change if you want it.
- Ruff flags a formatting issue in the existing `test_get_signal_stats_with_signal_id_filter` assertion (around line 221). It was already there before my change, and I didn't touch it.