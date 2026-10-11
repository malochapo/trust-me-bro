Four commits since 2025-05-22 changed how snooze or dedup decisions are made. Only one of them touched a time window, and that change left the UI and the backend disagreeing about units. I did not change any code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*. Canary instances are skipped by dedup entirely. They are also excluded from the pool of instances that dedup matches against, in both the default and filter-based paths. Snooze is not affected.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The window for signals with no dedup filter was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, which defaults to **45 minutes** (2700 seconds as applied).

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*. Despite the title, this changed behavior in two ways:
   - The warnings for filters with no mode or no action are gone. Such filters are now skipped silently.
   - An expired snooze filter used to `continue`, so later snooze filters were still checked. It now `break`s, so the loop stops at the first expired snooze filter and the remaining snooze filters are never evaluated.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*. This commit changed the units of per-filter dedup windows:
   - Before: `timedelta(minutes=f.window)`, so the value was read as minutes.
   - After: `_window_start(f.window)`, which subtracts `f.window` **seconds**, with a comment saying `SignalFilter.window` is stored in seconds.
   - Existing filters are now 60 times shorter than they were. A value of 15 used to mean 15 minutes and now means 15 seconds. The commit includes no migration and no UI change.

**Windows as the code applies them today**

- **Default dedup (signal has no dedup filter):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default 45) × 60, so 2700 seconds. It only matches instances that already have a case.
- **Per-filter dedup:** `SignalFilter.window`, in **seconds**. The model column defaults to 3600 (1 hour). The Pydantic create/base schema defaults to 600 (10 minutes). Neither default changed in the date range.
- **Snooze:** there is no lookback window. A snooze lasts until its `expiration` timestamp.

**Mismatch to be aware of:** `SignalFilterCreateDialog.vue` labels the field "Window (minutes)" and offers 5, 10, 15, 20, 30. It sends that value unconverted. Since `917a0b7b`, a user who picks 5–30 gets a 5–30 **second** window. The filter docstring in `filter_signal` still says "1-hour window", which is stale because the default is 45 minutes.

**Not decision changes:** `4474af25` only logs outcomes. `d2675cf4` masks raw fields before processing and does not change snooze or dedup logic. `5e136d7b` adds UI views and a schema relationship.

I found these through commit-message greps, pickaxe searches on `dedup`, `snooze`, `window`, and `lookback`, and per-file history for the signal modules. I did not run the test suite.

----- next turn -----

**Cause:** commit `917a0b7b` (2025-08-14, *share the lookback window computation*). It changed the per-filter window from `timedelta(minutes=f.window)` to seconds. A window of 30 became 30 seconds, so the two instances ten minutes apart fell outside it and opened two cases.

**Fix:** the UI and the existing stored values both mean minutes, so I restored minutes. Existing filters need no edit or migration.

- `src/dispatch/signal/service.py`: `filter_dedup` now computes `_window_start(f.window * 60)`, with a comment that `SignalFilter.window` is in minutes.
- `src/dispatch/signal/models.py`: the column default changed from `60 * 60` to `60`, so it still means one hour under the minutes unit. The comment now says minutes.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. It creates an instance with a case ten minutes ago, sets a 30-minute filter window, and asserts that the new instance is deduplicated into that case. I temporarily restored the seconds line and confirmed the test fails, then restored the fix.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped. I did not run the full suite.

**Choices to review:**
- The Pydantic `SignalFilterBase.window` default is still 600. Under minutes that is 10 hours, not 10 minutes. I left it alone because it only applies when the API receives no window, and the UI always sends one. Say if you want it changed.
- The docstring of `filter_signal` still says "1-hour window" for the default path. The default is 45 minutes, so that comment is stale. I did not touch it.
- Nothing is committed.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, *refactor(signal): simplify snooze filter checks*). It changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. The loop therefore stopped at the first expired snooze filter, so a valid snooze filter listed after it was never checked. The Okta user's new instances were not snoozed.

**Fix**
- `src/dispatch/signal/service.py`: the expired branch goes back to `continue`, so expired filters are skipped and the loop keeps going.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_snooze_expired_then_active`. It lists an expired snooze filter first and a valid one (expiring in 30 days) second, both matching the entity, and asserts the instance is snoozed. With `break` restored, the test fails; with the fix, it passes.

**Tests:** `python -m pytest tests/signal` gives 34 passed, 1 skipped.

**Notes**
- The test relies on `signal.filters` returning the filters in list order. That order is not guaranteed by the relationship, so the test could become flaky if that changes. I did not add an `order_by`.
- The earlier dedup window fix (the 30-minute case) is also still uncommitted, so the working tree now has changes from both reports. Nothing is committed.

----- next turn -----

**Recap of the fixes (uncommitted in the working tree)**

- **Dedup window in minutes (30-minute filter case).** Commit `917a0b7b` changed per-filter dedup windows from minutes to seconds, so a 30-minute window became 30 seconds. `filter_dedup` now converts the window from minutes again, and the column default in `models.py` is now 60 (minutes). Existing filters work unchanged. A regression test covers it.
- **Expired snooze blocking later snoozes (Okta case).** Commit `086dc910` changed the expired-snooze branch from `continue` to `break`, so one expired filter stopped evaluation of later valid ones. The branch is back to `continue`, with a regression test.
- **Stale docstring.** The `filter_signal` docstring still says the default window is 1 hour. It is 45 minutes. I did not change it.

Tests: `python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite. Nothing is committed.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES