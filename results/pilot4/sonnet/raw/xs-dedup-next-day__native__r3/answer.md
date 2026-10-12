Commit 917a0b7b ("refactor(signal): share the lookback window computation") caused the bug. It changed the filter window from minutes to seconds, so a window of 30 became 30 seconds. The UI field is labelled "Window (minutes)" and offers 5, 10, 15, 20 or 30, and the code before that commit used minutes.

**Fix:** in `src/dispatch/signal/service.py`, `_window_start` now takes minutes. Filter windows are read as minutes again, so existing filters work without edits. The default no-filter window passes its minutes value straight through, without the `* 60` that the refactor added.

**Test:** `test_dedup_filter_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a 30-minute filter and an instance for the same entity created 10 minutes earlier. It checks that a new instance is deduplicated into the existing case. It fails without the fix and passes with it. All of `tests/signal/test_signal_service.py` passes (15 passed, 1 skipped); I did not run the rest of the suite.

**Left alone:** the `window` column in `src/dispatch/signal/models.py` has a comment saying "seconds" and a default of 3600, which is inconsistent with minutes. That comment is probably what misled the refactor. I didn't change the default, because that would change behavior for filters that don't set a window.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES