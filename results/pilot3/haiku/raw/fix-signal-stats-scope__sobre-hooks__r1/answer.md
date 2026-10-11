Fixed: with a `signal_id`, the snooze counts in `GET /signals/{signal_id}/stats` now include only snooze filters attached to that signal. The unscoped `/signals/stats` path is unchanged and still counts every signal's filters.

**Cause:** `get_signal_stats` in `src/dispatch/signal/service.py` built the snooze-filter query from the entity expression alone and never applied `signal_id`. The instance counts were already correct because they filter on `SignalInstance.signal_id`.

**Change:**
- `src/dispatch/signal/service.py`: when `signal_id` is set, the snooze-filter query is restricted to filter ids found in `assoc_signal_filters` for that signal. I also added `assoc_signal_filters` to the `.models` import.
- `tests/signal/test_signal_stats_service.py`: new test `test_get_signal_stats_snooze_counts_scoped_to_signal_id`. Two signals each have a snooze filter matching the same entity, one active and one expired. It checks that the unscoped call counts both, and each scoped call counts only its own signal's filter.

**Verification:**
- The new test fails against the original `service.py` and passes with the fix.
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- I could not run `ruff` because it isn't installed here, so formatting and lint are unchecked.

I did not run the API endpoint itself, only the service function that backs it.