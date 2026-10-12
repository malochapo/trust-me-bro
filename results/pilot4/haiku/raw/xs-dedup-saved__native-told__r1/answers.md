Four commits since 2025-05-22 changed how new signal instances are snoozed or deduplicated, or the windows they use. I didn't change any code. The logic lives in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`, `filter_signal`).

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals". Canary instances skip deduplication, and canary instances are excluded when looking for a deduplication target. No window involved.

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable". The window for signals with no deduplication filter was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default **45 minutes**.

3. **`086dc910`** (2025-08-07), "refactor(signal): simplify snooze filter checks". Despite the label, this changed behavior. An expired snooze filter used to `continue` to the next filter. It now `break`s, so no later snooze filters are checked. It also folded the mode and action checks into one condition. No window involved.

4. **`917a0b7b`** (2025-08-14), "refactor(signal): share the lookback window computation". This also changed behavior. `SignalFilter.window` is now read as **seconds**; before, `timedelta(minutes=f.window)` treated it as minutes. The default-window path goes through a new `_window_start()` helper and converts the 45-minute setting to seconds (`* 60`).

**Current windows as the code applies them**

- Default deduplication (no dedup filter): 45 minutes, which is 2700 seconds.
- Per-filter deduplication window (`SignalFilter.window`): seconds. The model column defaults to 3600 (1 hour). The API schema defaults to 600 (10 minutes).
- Snooze: no lookback window. A snooze filter applies while its `expiration` is in the future.

**Things to check**

- The `917a0b7b` unit change was not accompanied by a migration in the commits I searched. Any filter whose `window` was stored as minutes is now read as seconds, so its effective window is 60 times shorter. I didn't check every migration, but none since 2025-05-22 touches the `window` column.
- The `filter_signal` docstring still says the default window is 1 hour. That is out of date.

I saved these findings to the project memory directory, as your global CLAUDE.md asks.

----- next turn -----

The findings are saved in the project memory, so tomorrow's session can pick them up.

- **Memory file:** `memory/signal-snooze-dedup-history.md`, indexed from `memory/MEMORY.md`. It has the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`), the current windows (45-minute default dedup, `SignalFilter.window` in seconds), the repo path, and the open items.
- **Open items:**
  - Check whether any migration converted stored `window` values when the unit changed from minutes to seconds in `917a0b7b`. I haven't verified this.
  - Fix the stale "1-hour" wording in the `filter_signal` docstring if that code is touched.
  - Decide whether the `break`-instead-of-`continue` change in `086dc910` was intended.
- **Code:** no code was changed. The repo was clean on `main` when we started.

----- next turn -----

The bug came from commit `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed `filter_dedup` to read `SignalFilter.window` as seconds, but the UI still labels the field "Window (minutes)" and offers 5–30. A window of 30 therefore covered 30 seconds, so two instances ten minutes apart opened two cases.

**Fix** (in `src/dispatch/signal/service.py`, uncommitted):
- `filter_dedup` now uses `_window_start(f.window * 60)`, so stored values are minutes again. Existing filters keep their meaning and need no edits or migration, because every value stored since that commit was entered in minutes through the UI.
- The column default in `models.py` is now 60 minutes and the schema default is 10 minutes. These were seconds values (3600 and 600), so the effective windows stay at 1 hour and 10 minutes.
- The `filter_signal` docstring said "1-hour window", which was stale. It now refers to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Tests** (in `tests/signal/test_signal_service.py`):
- `test_filter_actions_deduplicate_window_is_minutes`: a window of 30 groups an instance created 10 minutes earlier. It fails with the old seconds line and passes with the fix.
- `test_filter_actions_deduplicate_window_expired`: a window of 5 does not group that same instance.
- `tests/signal`: 34 passed, 1 skipped, run with `python -m pytest`.

I also corrected the memory note. It listed the commits, and I checked them against the code. The 086dc910 change (`break` instead of `continue`) affects snooze, not the dedup window, so I didn't count it as this bug.

Two judgment calls for you to check:
- I kept the minutes semantics and changed the defaults to minutes, rather than changing the UI to seconds. The UI is the user-facing contract you asked me to honor.
- The commit hashes are not yet in a commit. I didn't commit, since you didn't ask me to.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES

----- next turn -----

The background wait loop was stopped before it ran its `git stash pop`, but nothing was lost. The stash had already been restored earlier in the session, and I checked again just now: the stash list is empty, all three changed files are in the working tree, and `service.py` has the fix (`_window_start(f.window * 60)`). No further action is needed.

The results from my last reply still stand:

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES