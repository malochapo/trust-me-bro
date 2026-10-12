The bug came from `917a0b7b` (refactor(signal): share the lookback window computation, 2025-08-14). The UI and the stored `window` values are in minutes, but that commit started treating `f.window` as seconds. A 30-minute filter became a 30-second lookback, so two instances ten minutes apart didn't group.

Note that I don't have yesterday's list. I rebuilt it from `git log --since=2025-05-22` on the signal modules, and this commit is the one that breaks the window. `7a9fe810` introduced the minutes-based default window but didn't break filter windows.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and both the filter window and the default window use it. The `* 60` conversion for the default is gone.
- `src/dispatch/signal/models.py`: the column default is now 60 minutes and the schema default is 10 minutes. Both were in seconds before (3600 and 600).
- No stored filter needs editing. The UI always writes explicit minute values (5–30), so those keep their meaning.

**Regression test**
- `tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_in_minutes`: a 30-minute filter groups an instance from 10 minutes earlier and ignores one from 40 minutes earlier. It fails on the old code and passes now.
- `python -m pytest tests/signal tests/case`: 48 passed, 1 skipped. I did not run the full suite.

**Things to check**
- The docs (`docs/docs/administration/settings/signal/filter.mdx`) still say the default is one hour. I left them alone.
- A filter row created without a window now gets 60 minutes instead of 3600 minutes. That only matters for rows saved without a window, which the UI doesn't do.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES