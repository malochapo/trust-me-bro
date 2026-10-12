Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated, or changed the windows involved. No code was changed.

The logic is in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`, `_window_start`), with the default window in `src/dispatch/config.py`.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. `filter_dedup` returns early for canary instances, and canary instances are excluded from the dedup queries. No window change.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The window for signals with no dedup filter was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes** (2700 s) and can be overridden by environment variable.

3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. Two changes:
   - The separate mode and action checks were merged into one `continue`, and the missing-mode and missing-action warnings were dropped.
   - In the expired-snooze branch, `continue` became `break`. The first expired snooze filter now stops evaluation of all later filters, including active snooze filters that have not expired.

4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. The explicit-filter window changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats `SignalFilter.window` as **seconds**. Existing filters that were stored in minutes now look back 60 times less far. The UI still labels this field "Window (minutes)" with options 5, 10, 15, 20, 30, so a 15 now means 15 seconds. I did not trace the form payload end to end, but the field appears to be sent as-is. This change is under a refactor title, so it is easy to miss.

**Current values as the code applies them**
- Default dedup window (no dedup filter): 45 minutes (2700 s), configurable.
- Explicit dedup filter window: seconds. The API schema default is 600 s (10 min) and the database column default is 3600 s (1 h). The schema default is what applies to filters created through the API.
- Snooze: no lookback window. It is governed only by the filter's expiration timestamp.

**Stale or out of scope**
- The `filter_signal` docstring still says "1-hour window", which no longer matches the 45-minute default.
- `flows.py` has a 5-second threshold that controls whether a deduplicated signal updates the case thread. That affects posting, not the dedup decision, so I left it out.

I saved these findings to the project memory directory for later sessions.

----- next turn -----

The findings are saved in `/tmp/sobre-bench-work/run-f22b6532c346/home/.claude/projects/-tmp-sobre-bench-work-run-f22b6532c346-repo/memory/signal-snooze-dedup-history.md`, and it is indexed in `MEMORY.md`. Tomorrow's session will load both.

The memory note has:
- The four commits since 2025-05-22 that changed snooze/dedup decisions or their windows: `a348bbd2`, `7a9fe810`, `086dc910`, and `917a0b7b`.
- The current window values: the 45-minute default dedup window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`), explicit dedup filter windows in seconds (API default 600 s), and snooze governed only by expiration.
- Two open items I have not verified: whether the UI form sends the window value unchanged, and whether existing filter rows need a conversion. The first matters most. If the UI sends values unchanged, filters created there (labelled "minutes", options 5–30) now look back only seconds.
- The repo state: investigation only, no code changed, clean on `main` at `51546e13`.

I made no code changes and have not committed anything.

----- next turn -----

**The cause is `917a0b7b`** (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the explicit-filter window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. The UI offers 5–30 labelled "Window (minutes)" and sends the number unchanged, so a 30-minute filter became a 30-second lookback. Two instances ten minutes apart fall outside that and open two cases. The commit title called it a refactor, but it was a unit change.

I ruled out the other candidates from the list:
- `086dc910` changed the expired-snooze branch from `continue` to `break`. That affects snooze, not the dedup window.
- `7a9fe810` only made the no-filter default configurable.
- `a348bbd2` is the canary change and does not touch the window.

**Fix** (uncommitted, in the working tree):
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`, so the stored value is minutes again. Existing UI filters store minutes, so they work without edits or a migration. I also corrected the `filter_signal` docstring, which said "1-hour window" when the default is 45 minutes.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default went from 3600 seconds to 60 minutes, and the comment now says minutes.
- `tests/signal/test_signal_service.py`: two new tests. `test_deduplicate_filter_window_is_in_minutes` puts an instance ten minutes old with a 30-minute filter and expects deduplication. `test_deduplicate_filter_window_expired` uses a 5-minute filter with the same setup and expects no deduplication.

**Verification:** the regression test fails on the pre-fix `service.py` and passes with the fix. `python -m pytest tests/signal tests/plugins/dispatch_slack/case` gives 43 passed, 1 skipped. I did not run the full suite.

**Choices to review:**
- I left the API schema default `window: int | None = 600` alone. Under minutes that is 10 hours, not the 10 minutes the code currently applies. Rows created through the API without a window since `917a0b7b` are ambiguous, so they may need a look.
- I did not commit.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES