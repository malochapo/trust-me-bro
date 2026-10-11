Fixed: when a signal id is given, the snooze counts now include only that signal's snooze filters. Without a signal id, `/signals/stats` still counts every signal's filters.

**Cause:** In `get_signal_stats` (`src/dispatch/signal/service.py`), the snooze-filter query matched filters by entity only and never used `signal_id`. Snooze filters attach to signals through the `assoc_signal_filters` table, so the query now restricts to filter ids linked to that signal when `signal_id` is set.

**Change:**
- `src/dispatch/signal/service.py`: when `signal_id` is set, the snooze query filters `SignalFilter.id` to those in `assoc_signal_filters` for that signal. I also imported `assoc_signal_filters`. The instance counts are untouched.
- `tests/signal/test_signal_stats_service.py`: new test `test_get_signal_stats_snooze_counts_scoped_to_signal_id`. Two signals share one entity. Signal 1 has an active and an expired snooze filter, signal 2 has one active filter. It checks per-signal counts and the unscoped totals.

**Verification:**
- `python -m pytest tests/signal -q`: 33 passed, 1 skipped.
- The new test fails on the original code (`assert 2 == 1`) and passes with the fix.
- I didn't run the formatter because neither `ruff` nor `black` is installed here.

Nothing is committed.