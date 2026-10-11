Snooze counts now respect the `signal_id` scope, and a regression test covers it. The signal test directory passes (33 passed, 1 skipped), and the new test fails on the original code (`assert 2 == 1`).

**Cause:** `get_signal_stats` in `src/dispatch/signal/service.py` counted `SignalFilter` rows matching the entity, but never applied `signal_id`. The `signal_id` filter was applied only to the instance-count query. The link between signals and filters lives in the `assoc_signal_filters` table, which was never consulted.

**Fix:** When `signal_id` is given, the snooze-count query now restricts `SignalFilter.id` to the filter ids linked to that signal in `assoc_signal_filters`. Without `signal_id`, the query is unchanged, so every signal's filters still count.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal_id` in `tests/signal/test_signal_stats_service.py`. Two signals share one entity. Signal 1 has one active snooze filter, and signal 2 has one active and one expired. It checks the unscoped totals (2 active, 1 expired) and the per-signal values (1/0 and 1/1).

I didn't commit anything.

**Things I noticed but left alone:**
- The snooze query doesn't check `action == snooze`, so non-snooze filters (e.g. `deduplicate`) matching the entity are also counted as snoozes. The report didn't mention it, so I didn't change it. It's a one-line addition if you want it.
- `ruff format --check` flags a line in the existing test file (around line 220, in the pre-existing `test_get_signal_stats_with_signal_id_filter`). That's not from my change. `ruff check` passes on both files.