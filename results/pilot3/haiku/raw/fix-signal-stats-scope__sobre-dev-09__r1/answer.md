Fixed: `GET /api/v1/{organization}/signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. The unscoped `/signals/stats` path is unchanged.

**Cause:** in `get_signal_stats` (`src/dispatch/signal/service.py`), the snooze-filter query never looked at `signal_id`. It matched every `SignalFilter` whose expression referenced the entity, regardless of which signal the filter belonged to. The instance counts were already filtered by signal, which is why they were correct.

**Change:** when `signal_id` is set, the snooze query now restricts `SignalFilter.id` to the rows in `assoc_signal_filters` for that signal. I also added `assoc_signal_filters` to the `.models` import in that file.

**Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal_id` in `tests/signal/test_signal_stats_service.py`. Two signals share one entity: signal1 has an active snooze filter and signal2 has an expired one. It checks that the unscoped call counts 1 active and 1 expired, and that each signal-scoped call sees only its own filter.

**Verification:**
- The new test fails on the original code (`assert 1 == 0` on the expired count for signal1) and passes with the fix.
- `python -m pytest tests/signal` passes: 33 passed, 1 skipped.

I couldn't run a formatter because `ruff` isn't installed in this environment, so the edits were not formatter-checked.