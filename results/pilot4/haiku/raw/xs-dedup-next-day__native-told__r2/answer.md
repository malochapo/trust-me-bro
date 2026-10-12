The commit that broke deduplication windows is `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed `SignalFilter.window` from minutes back to seconds in `filter_dedup`, while the UI ("Window (minutes)", 5/10/15/20/30) and all stored filters use minutes. A window of 30 therefore meant 30 seconds, so two instances ten minutes apart never matched.

**Fix**
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`, so a filter's window is in minutes. Existing filters need no edits because their stored values are already minutes.
- `src/dispatch/signal/models.py`: the column default went from 3600 to 60 and the comment now says minutes. The old default was 60 hours under the correct unit. This is a Python-side default, so no migration is needed.
- `service.py`: the `filter_signal` docstring said "1-hour window" for the default rule. It now names the setting and its 45-minute default.

**Tests**
- Added two tests to `tests/signal/test_signal_service.py`:
  - `test_filter_deduplicate_window_is_in_minutes`: a window of 30 groups an instance from 10 minutes earlier. This test fails without the fix.
  - `test_filter_deduplicate_window_excludes_instances_outside_window`: an instance from 45 minutes earlier is not grouped.
- `python -m pytest tests/signal`: 34 passed, 1 skipped. I did not run the full suite.
- Changes are uncommitted.

**Not changed**
- The pydantic `SignalFilterBase.window` default is still 600. Under minutes that is 10 hours, which is probably not what was intended. It only applies when an API client omits the window, so I left it for you to decide.

**Canary:** `a348bbd2` ("fix(signal): don't dedup on canary signals") is the commit that changed canary deduplication. Canary instances are now skipped in both dedup paths.

**Default window:** signals with no filter use a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES