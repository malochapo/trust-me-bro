Four commits since 2025-05-22 touch snooze or dedup logic. I changed no code. My review was limited by the remaining budget (about $0.002 of $3 used), so I did not read the full snooze path or the dedup-related commit 5e136d7b.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - `filter_dedup` returns early for canary signals, so they are never deduplicated.
   - Canary instances are also excluded from the candidate query, so they are never treated as duplicates of other signals.
   - No time window involved.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - Adds `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default **45 minutes**.
   - `filter_dedup` previously used a hard-coded 1 hour (`timedelta(hours=1)`). It now uses the configured value.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - Folds the separate mode and action checks in `filter_snooze` into one condition, `f.mode != active or f.action != snooze`.
   - The inner loop's `continue` became `break`. That is a control-flow change, not just a simplification, and the commit message does not say so.
   - No time window involved.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Adds `_window_start(seconds)`, which returns `now - seconds`.
   - The default dedup window is now `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, so it is still **45 minutes**.
   - **Unit change:** the per-filter dedup window `f.window` was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as **seconds**. The added comment says `SignalFilter.window` is stored in seconds. The commit message does not mention this, and I did not verify where the value is stored. If it really was minutes before, every existing per-filter dedup window now covers 1/60 of the intended time.

**Windows as the code applies them today**

- Default dedup window: **45 minutes** (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, converted to seconds before use).
- Per-filter dedup window (`SignalFilter.window`): applied as **seconds**, per the comment in `917a0b7b`.
- Snooze: I did not find a time window in `filter_snooze`. I did not check whether snooze expiry is handled elsewhere.
- `tests/signal/test_signal_service.py:396` still says "1-hour window", which is stale against the 45-minute default.

**Not checked**

- `5e136d7b` (2025-07-03, entity and trigger views) matched the dedup keyword search. I did not inspect it, and it may not change dedup behavior.

----- next turn -----

The window bug came from `917a0b7b` (refactor(signal): share the lookback window computation). It is fixed, and the signal test suite passes (34 passed, 1 skipped).

**Cause:** The UI labels the window "Window (minutes)" with options 5–30, and existing rows store that number as minutes. Before `917a0b7b`, `filter_dedup` converted it with `timedelta(minutes=f.window)`. That commit passed the raw value into `_window_start`, which takes seconds. A window of 30 therefore became 30 seconds, so an instance ten minutes earlier fell outside it and opened a second case.

**Fix** (`src/dispatch/signal/service.py`):
- The lookback now uses `_window_start(f.window * 60)`. Existing filters keep their stored values and need no edits.
- The `filter_signal` docstring said "1-hour window" for the default. It now names `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Related change** (`src/dispatch/signal/models.py`): The `SignalFilter.window` column default was 3600 with a "seconds" comment, and the Pydantic schema default was 600. Both would mean hours if read as minutes. I changed them to 60 minutes and updated the comment. Existing rows are unaffected. This was not strictly required by the bug, so say if you'd rather keep it separate.

**Regression tests** (`tests/signal/test_signal_service.py`):
- `test_filter_actions_deduplicate_window_is_in_minutes`: window 30, previous instance ten minutes old, expects deduplication into the existing case. I confirmed it fails when the `* 60` is removed.
- `test_filter_actions_deduplicate_window_excludes_older_instances`: window 30, previous instance forty minutes old, expects no deduplication.

**Other commits:** The canary change is `a348bbd2` (fix(signal): don't dedup on canary signals, #6026). `7a9fe810` made the default window configurable and did not cause this bug.

**Default window:** Signals without a filter use `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes (`src/dispatch/config.py`).

**Caveats:**
- I had no record of yesterday's list in this session, so I took the commits from `git log --since=2025-05-22` and traced the window code through them.
- `ruff` is not installed here, so lint was not run.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES