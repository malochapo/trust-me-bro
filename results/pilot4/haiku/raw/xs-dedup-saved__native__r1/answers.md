I found four commits since 2025-05-22 that changed snooze or dedup decisions. I made no code changes.

**Commits**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - Canary signal instances skip deduplication entirely in `filter_dedup`.
   - Canary instances are also excluded from the candidate matches for both the default and the custom dedup queries.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - The default dedup window (for signals with no dedup filter) went from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
   - The config defaults to 45 minutes (`src/dispatch/config.py:95`). The code converts it to seconds (`* 60`), so the effective window today is 2700 seconds.

3. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Adds `_window_start(seconds)` and uses it for both windows.
   - Custom dedup filter windows were previously applied as `timedelta(minutes=f.window)`. They are now applied as seconds, so `f.window` is treated as seconds. This is a behavior change for any existing filter.

4. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - Folds the mode and action checks into one condition.
   - Changes an expired snooze filter from `continue` to `break`. Previously the loop skipped the expired filter and checked the rest. Now the first expired snooze filter stops the loop, so later active snooze filters on that signal are not evaluated.

**Current values and units**

- **Snooze:** no window. A snooze filter applies while its `expiration` is in the future. Filters without an expiration are skipped with a warning.
- **Default dedup (no dedup filter on the signal):** 45 minutes (2700 seconds), via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **Custom dedup filter window (`SignalFilter.window`):** seconds.
  - The model column defaults to 3600 seconds (1 hour).
  - The API schema default is 600 seconds (10 minutes).

**Mismatch to be aware of:** the filter dialog is labelled "Window (minutes)" and offers 5, 10, 15, 20, 30. I could not find any conversion in the UI code, so it appears to send those numbers unchanged. The backend reads them as seconds, so a user who picks "15 minutes" gets a 15-second window. This discrepancy came from `917a0b7b`, which changed the backend unit without changing the UI. I did not confirm the full save path in the store, so treat this as likely rather than verified.

**Other notes**
- The `filter_signal` docstring still says the default window is 1 hour. It is 45 minutes now.
- I left out commits that touch snooze or dedup only in UI or logging code, such as `5e136d7b` and `4474af25`. They do not change the decision logic.

----- next turn -----

I saved the findings to memory so tomorrow's session can pick them up.

- **File:** `memory/signal-snooze-dedup-history.md`, with an index line in `MEMORY.md`.
- **Contents:** the four commits (`a348bbd2`, `7a9fe810`, `917a0b7b`, `086dc910`), the current windows and their units, and the open question about the filter dialog's unit label.
- **Open item:** the dialog says "minutes" but appears to send the values unchanged, which the backend reads as seconds. I haven't confirmed the save path end to end, so the note marks it as unverified. The `filter_signal` docstring that still says 1 hour is also noted.

No code was changed.

----- next turn -----

The bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed custom deduplication windows from minutes to seconds, so a window of 30 grouped only 30 seconds of instances. Your two instances ten minutes apart fall outside that, so they opened two cases.

**The root cause**

- Since 2023 (`9c523348`), the backend read `SignalFilter.window` as minutes, which matches the dialog's "Window (minutes)" label and its 5/10/15/20/30 options.
- `917a0b7b` replaced `timedelta(minutes=f.window)` with a seconds-based helper and never changed the UI or the stored values, so existing filters silently shrank.

**The fix**

- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The custom-filter path and the default path both use it in minutes, and the stale "stored in seconds" comment and "1-hour" docstring are corrected.
- `src/dispatch/signal/models.py`: the model default is now 60 (one hour, as its comment already said), and the API schema default is now 10 minutes. The old values, 3600 and 600, were seconds-era numbers that would have become 2.5 days and 10 hours under minutes. This changes what new filters get if they omit `window`. Existing stored values are untouched, so existing filters need no edits or migration.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_in_minutes`, with a 30-minute window. An instance 10 minutes old must be deduplicated, and one 40 minutes old must not.

**Verification**

- The regression test fails on the buggy `service.py` (the 10-minute case) and passes with the fix.
- `python -m pytest tests/signal`: 34 passed, 1 skipped.

**Caveat**

A filter created through the API after `917a0b7b` with a seconds value would now be read as minutes. The stored data cannot distinguish those from UI-created filters, so I did not add a migration. If you have such filters, they need a review.

I also updated the memory note, which had listed this mismatch as unverified.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES