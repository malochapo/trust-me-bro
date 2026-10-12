The bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed how a filter's window is read, and the fix is in place. The new regression test passes with the fix and fails without it.

**What broke:** The commit changed `filter_dedup` from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. The UI's filter form is labelled "Window (minutes)" with options 5–30, and nothing migrated stored rows. So a window of 30 became 30 seconds, and two instances ten minutes apart were not grouped.

**What I changed:**
- `src/dispatch/signal/service.py`: `filter_dedup` reads `f.window` as minutes again (`_window_start(f.window * 60)`). I also corrected the `filter_signal` docstring, which said "1-hour window" when the default is 45 minutes.
- `src/dispatch/signal/models.py`: the column default and the Pydantic default for `window` are now 60 (minutes), so new filters without a window get one hour. The Pydantic default was 600, which would be 10 hours under minutes semantics. The column default was 3600, which would be 60 hours. The column default is Python-side, so no migration is needed.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_minutes`, parametrized over a window of 30 with instances 10 minutes apart (must deduplicate) and 40 minutes apart (must not). I also added a top-level `import pytest` for the parametrize decorator.

**Tests:** `python -m pytest tests/signal tests/case` gives 49 passed, 1 skipped. I did not run the full suite. I did not commit.

**Choices and risks:**
- Filters created through the UI since `917a0b7b` store minutes, so they work unchanged. Filters created via the API after that commit with seconds-sized values (e.g. 600) will now be read as minutes. Those rows can't be told apart from minute-based ones, so they may need a manual check.
- My earlier notes in memory say the window is in seconds. Those notes are now out of date.

I took the commit list from yesterday's memory note and checked each commit against the code and the UI rather than relying on the note alone.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES