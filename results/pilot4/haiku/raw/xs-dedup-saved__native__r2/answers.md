No code was changed. Four commits since 2025-05-22 changed the snooze or dedup decision logic in `src/dispatch/signal/service.py`, or the windows it uses. Two of them are labelled as refactors but change behavior.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - Canary instances skip deduplication entirely.
   - Canary instances are also excluded from the candidate matches in both dedup branches (the default branch and the filter-expression branch).
   - No time window involved. Snooze is not affected.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - Before: the default dedup window was hard-coded to 1 hour.
   - After: it comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default 45, in minutes. The code multiplies by 60 to get seconds.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - Merged the separate mode and action checks into one condition. Removed the "has no mode" and "has no action" warnings.
   - Behavior change: when a snooze filter has expired, the loop went from `continue` to `break`. Before, the loop moved on to the next filter. Now any later active snooze filters on the signal are never evaluated. Whether that matters depends on filter order, which the code doesn't define.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Added `_window_start(seconds)`.
   - Behavior change: the filter-expression dedup window went from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. A stored `window` of 600 used to mean 10 hours and now means 10 minutes. The column comment and the code have always said seconds, so this is a fix to match the documented unit, but it changes existing filters' behavior without saying so.

**Windows as the code applies them today**

- **Snooze:** no lookback window. A snooze filter applies until its `expiration` datetime. An expired filter stops the loop (see commit 3). A filter with no expiration is skipped with a warning.
- **Default dedup** (signal has no filters): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes** (2700 s). Matches the most recent instance of the same signal that has a case.
- **Filter dedup** (signal has filters): `SignalFilter.window`, in **seconds**.
  - The DB column default is **3600 s** (1 hour) (`src/dispatch/signal/models.py:206`).
  - The API schema default is **600 s** (10 minutes) (`models.py:282`).
  - If `window` is explicitly null, `_window_start(None)` would raise a `TypeError`. I did not run this. It is read from the code.

**Checked and excluded:** `4474af25` (adds logging only), `d2675cf4` (redacts raw fields before entity extraction, not the snooze or dedup decision), and `dee1699d` (unrelated project setting). The `expiration` hits in `5e136d7b` and `01c28ff0` did not touch `service.py`, so I did not check them further.

----- next turn -----

I saved the findings to memory so tomorrow's session can pick them up:

- `signal-snooze-dedup-history.md` in the project memory directory. It records the four commits, the current windows and their units, and the two "refactor" commits that changed behavior.
- `MEMORY.md`, the index file, with a one-line pointer to that memory. I created it because it didn't exist yet.

Nothing in the repo was changed, and the working tree is still clean. The main thing to pick up tomorrow is whether `086dc910` (`continue` → `break` on expired snoozes) and `917a0b7b` (minutes → seconds for filter windows) were intended. Both change live behavior, so they need your decision before any fix.

----- next turn -----

The regression came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the filter window from minutes to seconds, so a stored 30 became 30 seconds. The two instances ten minutes apart fell outside that window and opened separate cases.

**Evidence:** The UI labels the field "Window (minutes)" with options 5–30. Commit `9c523348` (2023) made the code use minutes to match. `917a0b7b` switched it back to seconds without touching the UI. The model comment and column default still said seconds, which was stale.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter path and the no-filter default both pass minutes, so existing stored filters (e.g. 30) work without edits.
- `src/dispatch/signal/service.py`: the `filter_signal` docstring now names `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` instead of a fixed 1-hour window.
- `src/dispatch/signal/models.py`: the column default is 60 minutes (1 hour), with the comment corrected. The old default of 3600 would have meant 60 hours under minutes. This only applies to rows inserted without a window, so existing rows are unaffected.
- `tests/signal/test_signal_service.py`: two regression tests. One checks that a 30-minute window groups an instance from 10 minutes earlier. The other checks that a 5-minute window does not. The first fails on the old code and passes now.

**Verification:** `python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite. Nothing is committed.

**Not changed, for you to decide**
- `086dc910` changed `continue` to `break` for expired snoozes in `filter_snooze`. Once one snooze has expired, later snooze filters on the same signal are skipped. It is a snooze bug, not the window bug, so I left it alone.
- The API schema default for `window` is still 600. That now means 600 minutes (10 hours) when the field is omitted. This matches the behavior before the regression, but it may be worth reviewing.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES