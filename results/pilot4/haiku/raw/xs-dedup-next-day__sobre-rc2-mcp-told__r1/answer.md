The window bug came from 917a0b7b (`refactor(signal): share the lookback window computation`). It fixed the UI-reported behaviour, but only for filters created after it. Filters you already had are stored in minutes, and the commit started reading them as seconds. So a window of 30 became 30 seconds, and two instances ten minutes apart didn't group.

**Fix**
- `src/dispatch/signal/service.py`: `filter_dedup` now reads `f.window` as minutes again (`_window_start(f.window * 60)`), so existing filters work without edits. The default-window path already multiplied `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60 and was correct.
- `src/dispatch/signal/models.py`: the `window` column comment said seconds and its default was `60 * 60`. It now says minutes with default `60`, which keeps the one-hour default. This is a Python-side default, so no migration is needed. Existing rows are untouched.
- `filter_signal`'s docstring now names the setting instead of "1-hour".
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_in_minutes`. It creates an instance 10 minutes old and a new one, under a window-30 filter, and expects deduplication. I confirmed it fails with the seconds line restored and passes with the fix.

**Test results**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- I did not run the full suite.

**Other findings**
- 086dc910 (`simplify snooze filter checks`) changed `continue` to `break` in the expired-snooze branch of `filter_snooze`. One expired snooze filter now stops evaluation of the remaining snooze filters for that signal. This is a separate bug in snoozing, which I did not fix.
- The API schema default in `SignalFilterBase` is `window: int | None = 600`. Under the minutes meaning that is 10 hours, not the 1 hour the column default implies. I left it alone because changing it affects API clients.

The commit list I used is from `git log --since=2025-05-22` filtered to signal, dedup and snooze files. I could not see yesterday's list in this conversation.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES