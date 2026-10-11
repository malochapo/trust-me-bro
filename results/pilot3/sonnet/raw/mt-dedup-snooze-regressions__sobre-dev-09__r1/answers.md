Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. Their effect is in `filter_snooze` and `filter_dedup` in `src/dispatch/signal/service.py`. I only read the code and history and changed nothing.

1. **`a348bbd2`, 2025-05-29, "don't dedup on canary signals" (#6026).**
   - `filter_dedup` now returns early, with no dedup, if the incoming instance is a canary.
   - Canary instances are also excluded from the candidate-match queries, both the default one and the per-filter one.
   - It added no time window and changed none.

2. **`7a9fe810`, 2025-06-19, "make the default deduplication window configurable".**
   - This is the window for signals that have no filters. It was a hard-coded `timedelta(hours=1)` and now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
   - The setting is an env var cast to int, with a default of **45 minutes**. That is a change from the old 1 hour.

3. **`086dc910`, 2025-08-07, "simplify snooze filter checks".**
   - It collapsed the separate mode and action checks in `filter_snooze` into one condition: skip any filter that isn't active or isn't a snooze action.
   - The old warnings for a filter with no mode or no action are gone.
   - Behaviour change: when a snooze filter's `expiration` has passed, the code now does `break` instead of `continue`. An expired snooze filter therefore stops the loop, and any later filters on the signal are not checked for snoozing.
   - Snooze uses an absolute `expiration` timestamp (compared in UTC), not a lookback window.

4. **`917a0b7b`, 2025-08-14, "share the lookback window computation".**
   - It added the helper `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - The default window is now passed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, which still comes to 45 minutes.
   - Behaviour change: the per-filter dedup lookback used to be `timedelta(minutes=f.window)`. It now treats `f.window` as seconds. The model column and its comment say seconds, defaulting to `60*60`, i.e. 1 hour. The Pydantic schema default in `models.py:282` is `600`, i.e. 10 minutes.
   - The old code read `f.window` as minutes, so any value stored before the change gets a much shorter lookback now. For example, a stored 60 used to mean 60 minutes and now means 60 seconds.

**Windows as applied today**

| Case | Window |
|---|---|
| Signal with no filters | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default 45 minutes), converted to seconds |
| Signal with dedup filters | `SignalFilter.window` in seconds (DB default 3600 s, schema default 600 s) |
| Snooze | until the filter's `expiration` timestamp, with no window |

----- next turn -----

`917a0b7b` ("share the lookback window computation", 2025-08-14) caused it.

Before that commit, the per-filter lookback was `timedelta(minutes=f.window)`. That commit changed it to read `f.window` as seconds, because the model comment says seconds. The UI dialog, though, is labelled "Window (minutes)" and offers 5, 10, 15, 20 and 30, and stores those numbers as they are. So a window of 30 became 30 seconds, and two instances ten minutes apart no longer matched, so each opened its own case.

**Fix.** In `filter_dedup` in `src/dispatch/signal/service.py`, the filter window is now passed as `f.window * 60`. A stored 30 means 30 minutes again, and existing filters work without any edit or data migration. The default no-filter window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, 45 minutes) is unchanged.

**Test.** I added `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It creates two instances for the same entity ten minutes apart, with a deduplicate filter set to 30. It fails on the old code and passes now. The rest of that file also passes (15 passed, 1 skipped).

**Left alone.** The `SignalFilter.window` column comment in `models.py` still says seconds, with a default of `60 * 60`. The Pydantic default of 600 is inconsistent in the same way. Read as minutes, those defaults would mean 60 hours and 10 hours. This was already the case before the regression, so I didn't change them without your say-so. Changing the DB default would need a migration, and the comment should be corrected either way.

I haven't committed anything.

----- next turn -----

The cause is `086dc910` ("simplify snooze filter checks", 2025-08-07). It changed the expired-filter branch of `filter_snooze` from `continue` to `break`. The first expired snooze filter now ends the loop, so a valid snooze filter listed after it is never checked. For "Okta: Impossible travel", the filter that expired last week comes first and hides the one valid until next month.

**Fix.** In `src/dispatch/signal/service.py`, an expired snooze filter is skipped again with `continue`, so later filters are still evaluated. The rest of that refactor is unchanged.

**Test.** I added `test_filter_actions_snooze_expired_filter_does_not_mask_valid_one` in `tests/signal/test_signal_service.py`. The signal gets two snooze filters for the same entity, an expired one first and a valid one second. The test checks that the instance ends up snoozed. It fails with the old `break` and passes with the fix. The full `tests/signal` suite passes: 34 passed, 1 skipped.

Nothing is committed. The working tree also holds the dedup-window fix from the last turn.

----- next turn -----

Two regressions from the August 2025 refactors are fixed in the working tree. Nothing is committed yet.

- **Dedup windows (`917a0b7b`).** The refactor changed the per-filter lookback from minutes to seconds, but the UI stores minutes. A window of 30 acted as 30 seconds, so related instances opened separate cases. The service now multiplies `f.window` by 60. Existing filters work without being edited. A regression test covers it.
- **Snoozing (`086dc910`).** An expired snooze filter now ended the loop (`break` instead of `continue`), so a valid snooze filter listed after it was never checked. It now skips the expired filter and keeps going. A regression test covers it.
- **Canary signals (`a348bbd2`).** This change was not a bug. Canary instances are no longer deduplicated, and they are excluded when looking for an existing case to group with.
- **Default window.** Signals with no filters use `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. `7a9fe810` made it configurable; before that it was a hard-coded 1 hour.
- **Left alone.** The `SignalFilter.window` column comment and default (3600) in `models.py` still describe seconds. The Pydantic default (600) is inconsistent in the same way. Fixing the DB default would need a migration.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES