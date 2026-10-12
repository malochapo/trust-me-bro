The cause is commit `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed `SignalFilter.window` from minutes to seconds without migrating stored data or updating the UI. A 30-minute filter therefore looked back 30 seconds, so two instances ten minutes apart opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and both the per-filter window and the default dedup window use it. The default window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds before this change and is now passed directly as minutes. The `filter_signal` docstring now refers to the setting instead of "1-hour window".
- `src/dispatch/signal/models.py`: the `window` column default is now `60` minutes (was `3600`, which was seconds). This is a Python-side default, so no migration is needed.
- Existing filters need no edits. Their stored values (5–30, as entered in the UI) were already minutes before the regression, and the UI label stays as it is.

**Regression tests** in `tests/signal/test_signal_service.py`:
- `test_filter_window_is_in_minutes`: a 30-minute filter groups an instance from ten minutes earlier. It fails on the old code and passes with the fix.
- `test_filter_window_excludes_instances_outside_window`: a 5-minute filter does not group that same instance.

`python -m pytest tests/signal tests/case tests/plugins/dispatch_slack` gives 58 passed and 1 skipped.

I left the Pydantic `SignalFilterBase.window` default at 600. It is now 600 minutes (10 hours) for API calls that omit `window`, which matches the pre-regression behaviour. Say if you want it changed.

The changes are uncommitted. I also updated the memory note for this topic.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES