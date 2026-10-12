I found five commits since 2025-05-22 that touch the snooze or dedup decision or its windows. I did not change any code. Dates are commit dates.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*
   - Canary signal instances skip deduplication entirely (`filter_dedup` returns early when `signal_instance.canary` is set).
   - Canary instances are also excluded as dedup matches in both the default and the filter-based paths.
   - No time window involved.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*
   - The default dedup window for signals with no dedup filter was hard-coded at 1 hour.
   - It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default 45), so the window is 45 minutes unless overridden.

3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*
   - Merged the separate mode and action checks into one `continue`. This also dropped the warning logs for filters with no mode or no action. The skip behaviour is unchanged.
   - **Behaviour change:** when a snooze filter's expiration has passed, the loop went from `continue` to `break`. An expired snooze filter now stops evaluation of any later active snooze filters on that signal. Before this commit they were still checked.

4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*
   - Added `_window_start(seconds)` and used it for both dedup windows.
   - **Unit change, not disclosed in the message:** the per-filter window was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats it as seconds. A filter window is now 60× shorter than before for the same stored number.
   - The default path converts explicitly: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`.

I also checked `d2675cf4` (masks raw fields before processing), `4474af25` (logs outcomes), `5e136d7b` and `90f73fe2` (UI). None of them change the snooze or dedup decision or its windows. `d2675cf4` does change the payload before entity extraction, so it could affect which entities an expression matches, but it does not change the windows.

**Current behaviour and values**

- **Snooze:** there is no lookback window. A snooze filter applies while `expiration` is in the future. Filters with no expiration are skipped with a warning. A filter with an expression snoozes only the instances it matches. A filter with no expression snoozes every instance of that signal. The loop stops at the first expired snooze filter (see commit 3).
- **Default dedup** (signal has no filters): 45 minutes, which is 2700 seconds. It matches the most recent earlier non-canary instance of the same signal that has a case, regardless of entities.
- **Filter dedup** (signal has dedup filters): `SignalFilter.window` is in **seconds**.
  - Model column default is 3600 seconds (1 hour).
  - API schema default is 600 seconds (10 minutes).
  - It matches earlier non-canary instances that satisfy the filter expression and share an entity with the new instance. The earliest match's case is reused.

**Likely bug to check (not changed)**

The UI dialog at `src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue` labels the field "Window (minutes)" with options 5, 10, 15, 20, 30. It sends those numbers unconverted. Since the backend (since `917a0b7b`) treats them as seconds, a 10-minute choice in the UI becomes a 10-second window. Either the UI should multiply by 60 or the label and backend should agree. Existing rows stored before `917a0b7b` may also have been written under the minutes assumption, so their meaning depends on when they were created.

----- next turn -----

I saved the findings to a project memory so tomorrow's session can pick them up:

- `memory/signal-snooze-dedup-history.md` holds the commit list with what each one changed, the current window values and units, and the open UI bug.
- `memory/MEMORY.md` has a one-line pointer to that file.

Both are under `/tmp/sobre-bench-work/run-305d7c47b69d/home/.claude/projects/-tmp-sobre-bench-work-run-305d7c47b69d-repo/memory/`.

Nothing in the repo was changed. The open item for tomorrow is the filter window mismatch: the UI labels the window in minutes (5–30) and sends it unconverted, but the backend treats it as seconds. Deciding whether the UI or the backend should change is still open.

----- next turn -----

The regression is from `917a0b7b` (refactor(signal): share the lookback window computation, 2025-08-14). That commit changed the per-filter dedup window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. A UI window of 30 became 30 seconds, so two instances ten minutes apart never matched. The UI and stored filters both use minutes, and the code was correct before that commit.

I checked the commit list from the earlier notes against the code, and it holds. The other candidates don't explain this bug. `086dc910` affects snooze, and `7a9fe810` only made the no-filter default configurable.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and `filter_dedup` uses it for both the no-filter default and per-filter windows. The no-filter default is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` converted to minutes, so the value is unchanged. I also corrected the `filter_signal` docstring, which still said 1 hour.
- `src/dispatch/signal/models.py`: the `window` column default is now `60` minutes and the API schema default is `10` minutes. Both keep the windows that are in effect today (1 hour and 10 minutes), now expressed in minutes.
- `tests/signal/test_signal_service.py`: two regression tests. One checks that a window of 30 groups an instance 10 minutes earlier. The other checks that an instance 40 minutes earlier falls outside that window. The first fails on the old code and passes with the fix.

**Verification**
- `python -m pytest tests/signal`: 34 passed, 1 skipped (baseline before the change was 32 passed, 1 skipped).
- Ruff isn't installed here, so I didn't run format or lint checks.

**Existing filters:** no edits are needed. Stored windows are minute values from the UI, and the backend now reads them that way again. The one exception is a row created through the API or the ORM without an explicit window. Its stored value is 600 or 3600 from the old defaults, and under the minutes reading it now means 10 or 60 hours instead of 10 minutes or 1 hour. Filters created through the UI are not affected. I didn't write a data migration for those rows.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES