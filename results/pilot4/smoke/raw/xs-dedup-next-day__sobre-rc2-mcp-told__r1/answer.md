The window bug is fixed: a filter's window now means minutes, as the UI says. Existing filters need no edits. The new regression test fails on the old code and passes with the fix, and all 34 signal tests pass (1 skipped).

**Cause:** commit `917a0b7b` ("refactor(signal): share the lookback window computation") changed `filter_dedup` to treat `SignalFilter.window` as seconds. Before it, the code used `timedelta(minutes=f.window)`. The UI offers 5, 10, 15, 20 or 30, and the docs describe the window as minutes, so a stored 30 became a 30-second lookback. Two instances ten minutes apart fall outside that window, so both opened cases.

**Fix** (`src/dispatch/signal/service.py`, `models.py`):
- `_window_start` now takes minutes, and both the per-filter window and the default window pass minutes to it.
- The `SignalFilter.window` column comment now says minutes, and its Python default is 60 (one hour) instead of 3600.
- Existing rows hold minute values from the UI, so they keep working as they are.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_deduplicate_window_is_minutes`. An earlier instance from ten minutes ago is deduplicated with window 30 and not with window 5. The module now imports `pytest` at the top.

**Answers:**
- The commit that broke deduplication windows is `917a0b7b`.
- The canary change is `a348bbd2` ("don't dedup on canary signals").
- Signals with no filter use a window of **45 minutes**, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45. The docs still say one hour, so they are out of date.

**Things I did not change:**
- Commit `086dc910` changed `continue` to `break` in `filter_snooze` when a snooze filter has expired. That can skip later active snooze filters. I did not touch it, but it looks like a real bug and is worth checking.
- The API schema default for `window` is still 600, which means 10 hours under the minutes meaning. I left it because changing it alters behaviour for filters created without a window.
- Ruff is not installed here, so I could not run the linter. I did wrap the one line that looked too long.
- I did not commit anything.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES