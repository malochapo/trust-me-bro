Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup, and one of them changed the unit of the dedup window. I didn't change any code.

**Commits (all in `src/dispatch/signal/service.py` unless noted)**

1. **`a348bbd2`** (2025-05-29, fix: don't dedup on canary signals). Canary instances are skipped in both dedup paths, the default one and the filter-based one. No window involved.

2. **`7a9fe810`** (2025-06-19, make the default dedup window configurable). Signals with no dedup filter used a hard-coded 1 hour. The window now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, which defaults to **45 minutes** (2700 s) and can be set by environment variable.

3. **`086dc910`** (2025-08-07, simplify snooze checks). The mode and action checks were merged into one condition. The commit also changed the expired-snooze branch from `continue` to `break`. Now, once an expired snooze filter is hit, the loop stops, so any later active snooze filters are never checked. This is a behavior change, not just a refactor.

4. **`917a0b7b`** (2025-08-14, share the lookback window computation). Added `_window_start(seconds)` and changed the per-filter dedup window from `timedelta(minutes=f.window)` to seconds, so `SignalFilter.window` is now read as **seconds**. The stored data and the UI were not changed.

**Windows as the code applies them today**
- Default dedup (no dedup filter): 45 min, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- Dedup filter window: `SignalFilter.window` in seconds. The model default is 3600 s (1 h). The pydantic schema default is 600 s (10 min).
- `src/dispatch/signal/flows.py:373`: a 5-second gate on sending updates for deduplicated signals. It has not changed since 2023, so it is not one of the commits above.

**Likely bug from `917a0b7b`:** `SignalFilterCreateDialog.vue` still labels the field "Window (minutes)" and offers 5, 10, 15, 20 and 30. Those values are now read as seconds, so a filter the UI creates with a 10-minute window dedups over 10 seconds. The `filter_signal` docstring also still says "1-hour window".

I saved these findings to project memory (`signal-snooze-dedup-history.md`) and added an index entry.

----- next turn -----

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