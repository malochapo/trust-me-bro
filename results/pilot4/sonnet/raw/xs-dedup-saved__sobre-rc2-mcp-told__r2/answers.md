Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. All are in `src/dispatch/signal/service.py`, and `7a9fe810` also touches `src/dispatch/config.py`. I only read the code and history; nothing was changed.

1. **`a348bbd2` (2025-05-29, "don't dedup on canary signals", #6026)**
   - `filter_dedup` now returns early if the incoming instance is a canary.
   - Canary instances are also excluded from the candidate matches, in both the no-filter default path and the per-filter path (`~SignalInstance.canary`).
   - It changed no time window.

2. **`7a9fe810` (2025-06-19, "make the default deduplication window configurable")**
   - Signals with no filters used a hard-coded 1-hour dedup window. That window now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
   - The setting is an int in minutes and defaults to **45**, not the old 60.
   - So the default window went from 60 to 45 minutes unless the environment variable overrides it.

3. **`086dc910` (2025-08-07, "simplify snooze filter checks")**
   - `filter_snooze` dropped the separate "no mode" and "no action" warnings. It now skips any filter that isn't `mode == active` and `action == snooze` in a single check.
   - There is one behaviour change. When a snooze filter's `expiration` is at or before now, the loop used to `continue` to the next filter. It now does `break`, so any later filters on that signal are no longer checked.
   - Expiration is an absolute timestamp, treated as UTC, rather than a window length.

4. **`917a0b7b` (2025-08-14, "share the lookback window computation")**
   - It adds `_window_start(seconds)`, which returns now (UTC) minus that many seconds. Both dedup paths now use it.
   - **Default path (no filters):** the window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is 45 minutes (2700 s) by default. The effective value is unchanged from `7a9fe810`.
   - **Per-filter path:** the window is `f.window`, now read as **seconds**. It was previously `timedelta(minutes=f.window)`. The model column `SignalFilter.window` defaults to `60 * 60`, which is 3600 s or 1 hour. The Pydantic schema default is `600`, which is 10 minutes.
   - The old code applied that same stored number as minutes. A stored 3600 was a 60-hour window, and it is now a 1-hour window. This is a real behaviour change, even though the commit is titled a refactor.

The default and per-filter windows are not the same unit. The default window is configured in minutes, then multiplied by 60. The per-filter window is stored in seconds.

I did not find any later changes to this logic. Commits such as `dece6805` (signal tags) and `d2675cf4` (masking raw fields) touched the same file but not the snooze or dedup decisions.

----- next turn -----

I saved the task, the findings and one decision to the sobre session. In a new session, call `sobre_session` with `action="load"` to bring them back.

- **Task:** which commits since 2025-05-22 changed snooze or dedup decisions and their time windows. This was read-only and no code was changed.
- **Findings:** the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`), what each changed, and the current window values:
  - The default no-filter window is 45 minutes (2700 s).
  - The per-filter `f.window` is read as seconds, and its column default is 3600 s.
  - The schema default is 600.
- **Decision and open follow-up:** `917a0b7b` switched the per-filter window from minutes to seconds. Tomorrow I could check whether UI or API callers, and any `SignalFilter.window` values already stored, still assume minutes.

I did not write a separate file to the memory directory. The session record covers it.

----- next turn -----

Commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14) caused it. The fix is in and tested.

**Cause:** the new `_window_start` helper treats its argument as seconds. The filter path passed it `f.window`, which the UI stores in minutes (the field is labelled "Window (minutes)" and offers 5–30). A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases. The commit also added a comment claiming the column was in seconds, which is wrong. The old `timedelta(minutes=f.window)` code was correct.

**Fix:**
- `_window_start` in `src/dispatch/signal/service.py` now takes minutes. Existing filters work unedited, because the stored values were always minutes.
- The no-filter path now passes the minutes setting directly instead of multiplying by 60.
- I corrected the misleading unit comments in `src/dispatch/signal/models.py`. The column default of 3600 and the schema default of 600 were also wrong for minutes, so both are now 60 (one hour). This only affects filters created without a window.

**Test:** `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a 30-minute filter and an earlier instance from 10 minutes before. It fails on the old code and passes now. All of `tests/signal` passes: 33 passed, 1 skipped.

My first draft of the test passed on the old code too. The filter wasn't attached to the signal, so the no-filter path was doing the dedup. I fixed that by adding the filter to the session before appending it.

The canary commit is `a348bbd2`. It makes canary instances skip deduplication and excludes them from the instances other signals dedup against.

The default window for signals without a filter is 45 minutes. It was a hard-coded hour until `7a9fe810` made it configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES