Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. All four are in `src/dispatch/signal/service.py`, and one also touches `src/dispatch/config.py`. I only read the history and code; nothing was changed.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns immediately if the incoming instance is a canary.
- Existing canary instances are also excluded from the dedup lookups, in both the default no-filter path and the per-filter path.
- It adds no time window and changes no window value.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default window used when a signal has no filters was hard-coded as `timedelta(hours=1)`.
- It is now read from the new setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, an int read from the environment with a default of **45 minutes**.
- This was a behaviour change as well as a refactor: the default dropped from 1 hour to 45 minutes.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- `filter_snooze` now skips any filter that isn't active or isn't a snooze action with one combined check. This replaces the separate checks that logged warnings for a missing mode or action.
- When a snooze filter's `expiration` has already passed, the code now does `break` instead of `continue`. Once an expired snooze filter is hit, the remaining filters are no longer evaluated, so a later, unexpired snooze filter is never checked.
- The snooze window is the filter's `expiration` timestamp, compared against the current UTC time. It is not a duration.
- A filter with no `expiration` is still skipped with a warning.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds `_window_start(seconds)`, which returns the current UTC time minus that many seconds, and both dedup paths now use it.
- The default path calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes (2700 s).
- The per-filter path changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats `f.window` as **seconds**.
- `SignalFilter.window` is an Integer column in `signal/models.py` whose comment says it is in seconds. Its default is `60 * 60`, which is 1 hour. The Pydantic schema field in the same file defaults to `600`, which is 10 minutes.
- This changes behaviour even though it is labelled a refactor. Before this commit, a stored value such as 3600 was read as 3600 minutes (60 hours). It is now read as 3600 seconds (1 hour). That aligns the code with the column definition.

**Values the code applies today**

| Case | Window |
|---|---|
| Dedup for a signal with no filters | 45 minutes (2700 s), configurable via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` |
| Dedup for a signal with a dedup filter | `SignalFilter.window` in seconds (column default 3600 s, schema default 600 s) |
| Snooze | until the filter's `expiration` timestamp (UTC) |
| Canary instances | never deduplicated, and ignored as dedup matches |

----- next turn -----

**Culprit: `917a0b7b` (2025-08-14), "share the lookback window computation".** It changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to seconds. The UI ("Window (minutes)", options 5–30) stores minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart no longer matched, and each opened its own case.

**Fix**
- `src/dispatch/signal/service.py`: the filter window is read as minutes again (`_window_start(f.window * 60)`). Stored values are already minutes, so existing filters work without edits or a migration.
- `src/dispatch/signal/models.py`: I also fixed the defaults, which had assumed seconds. The column default is now `60` (1 hour) instead of `3600`, and the API schema default is `10` (10 minutes) instead of `600`. With minutes, the old defaults would have meant 60 hours and 10 hours. This changes defaults for filters created without an explicit window, so say if you'd rather I leave them.

**Test:** I added `test_filter_actions_deduplicate_window_is_in_minutes`. It creates a filter with `window=30` and two instances ten minutes apart, and expects the newer one to be deduplicated.
- With the fix, `python -m pytest tests/signal` gives 33 passed, 1 skipped.
- With the source changes stashed, the new test fails as expected.

----- next turn -----

**Cause: `086dc910` (2025-08-07), "simplify snooze filter checks".** In `filter_snooze`, the expired-filter branch was changed from `continue` to `break`. When an expired snooze filter came first in the list, the loop stopped. The valid filter after it was never checked, so the instance wasn't snoozed. This was the same kind of mistake as the dedup window bug, in a commit labelled a refactor.

**Fix:** in `src/dispatch/signal/service.py`, that branch is back to `continue`, so an expired filter is skipped and the remaining filters are still checked.

**Test:** I added `test_filter_actions_snooze_expired_filter_before_valid_filter`. It gives a signal two snooze filters on the same entity, the first expired a week ago and the second valid for 30 days. It expects the instance to be snoozed.

- With the fix, `python -m pytest tests/signal` gives 34 passed, 1 skipped.
- With the source changes stashed, the new test fails. That stash also removed the earlier window fix, so it shows the test fails on the old code, not that this fix alone makes it pass.

The same commit also removed the warnings logged for a filter with no mode or no action. The combined check skips those filters silently now. That doesn't affect which instances are snoozed, so I left it.

----- next turn -----

**Recap**

Two regressions came from commits labelled as refactors, and both are fixed in the working tree. I haven't committed anything.

- **Dedup windows:** `917a0b7b` switched the per-filter lookback from minutes to seconds. The UI stores minutes (5–30), so a window of 30 acted as 30 seconds and instances ten minutes apart opened separate cases. The window is read as minutes again, so existing filters work unedited. I also changed the `SignalFilter.window` column default from `3600` to `60` and the API schema default from `600` to `10`, both now in minutes.
- **Snoozing:** `086dc910` changed `continue` to `break` for expired snooze filters. An expired filter listed before a valid one stopped the loop, so the valid snooze never applied. It is back to `continue`.
- **Tests:** I added a regression test for each fix. Both fail without the fixes, and `python -m pytest tests/signal` passes with them (34 passed, 1 skipped).
- **Other commits:** `a348bbd2` made canary signals skip deduplication and excluded them from dedup matches. `7a9fe810` made the default no-filter window configurable, changing it from 1 hour to 45 minutes.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES