Fixed. `GET /signals/{signal_id}/stats` now counts only the snooze filters attached to that signal, and the new regression test passes.

**Cause:** In `get_signal_stats` (`src/dispatch/signal/service.py`), the active/expired snooze query matched `SignalFilter` rows by entity expression alone. It never joined through `assoc_signal_filters`, so `signal_id` had no effect on it. Only the instance counts used `signal_id`, which is why they were already right.

**Fix:** When `signal_id` is given, the snooze query is restricted to filter IDs linked to that signal in `assoc_signal_filters`. I used an `IN` subquery rather than a join so the existing query shape stays the same. Without a `signal_id`, the query is unchanged, so `/signals/stats` still counts every signal's filters.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal` in `tests/signal/test_signal_stats_service.py`. Two signals share an entity: signal1 has one active snooze filter, and signal2 has one active and one expired. It checks the per-signal counts (1/0 and 1/1) and the unscoped total (2 active, 1 expired). It failed before the fix (`assert 2 == 1`) and passes after.

**Verification:** `python -m pytest tests/signal/` gives 33 passed, 1 skipped. `ruff check` passes on both changed files. `ruff format` flags one pre-existing line in the test file (an `assert` near line 296) that I left alone.

I haven't committed anything.