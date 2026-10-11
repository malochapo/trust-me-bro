Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All of them are in `src/dispatch/signal/service.py`, and `7a9fe810` also touches `config.py`. I only read the code and history, and changed nothing.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early, so no dedup happens, when the incoming instance is a canary.
- Both dedup queries, the default one and the per-filter one, now exclude existing canary instances with `~SignalInstance.canary`. A canary can no longer be the case that a new instance gets attached to.
- It adds no time window. It also rewrote a large part of `tests/signal/test_signal_service.py`.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- This changes the window used for signals that have no filters at all. It was hard-coded to 1 hour (`timedelta(hours=1)`).
- It now comes from the new setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`. The setting is read from the environment, cast to int, with a default of **45 minutes**.
- Because the default changed from 60 to 45, the behavior also changed for anyone who doesn't set the variable.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- In `filter_snooze`, the separate "no mode" and "no action" warn-and-skip checks are merged into one line: `f.mode != active or f.action != snooze` means skip.
- One behavior change: an expired snooze filter (`expiration <= now`, compared in UTC) now does `break` instead of `continue`. The rest of the signal's filters are no longer checked once an expired snooze filter is found.
- Snooze uses an absolute expiration timestamp, not a window. A filter with no expiration is skipped with a warning.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds a `_window_start(seconds)` helper, which returns `now(UTC) - timedelta(seconds=seconds)`.
- The default window is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, so **45 minutes = 2700 seconds** by default.
- The per-filter window is now `_window_start(f.window)`, so `SignalFilter.window` is read as **seconds**. The column default is `60 * 60`, which is 1 hour, and the pydantic schema default in `models.py` is 600, which is 10 minutes. Before this commit the code applied `timedelta(minutes=f.window)`, so a stored 3600 meant 3600 minutes. That was a unit bug, and this commit corrects it. Nothing else in the commit's own diff hints at it, since the message calls it a refactor.

**How the code applies them today**
- **Dedup, signal with no filters:** it looks back 45 minutes by default (configurable). It matches the most recent non-canary instance of the same signal that already has a case, and skips the instance being checked.
- **Dedup, signal with filters:** each active dedup filter looks back `filter.window` seconds. It matches non-canary instances that share entities with the new instance, and takes the earliest one's case.
- **Snooze:** it applies while `expiration` is still in the future, with no window involved.

----- next turn -----

The regression came from **`917a0b7b`** (2025-08-14, "share the lookback window computation"). It's labelled a refactor, but it changed the unit of `SignalFilter.window` from minutes to seconds.

The UI's "Window (minutes)" dropdown offers 5, 10, 15, 20 and 30, and it stores those numbers as they are. Before the commit, `timedelta(minutes=f.window)` read them correctly. After it, `_window_start(f.window)` read the same numbers as seconds, so a window of 30 became 30 seconds. Two instances ten minutes apart then fell outside the window and each opened its own case. The other three commits aren't involved: `a348bbd2` (canary) and `086dc910` (snooze) touch different logic, and `7a9fe810` only changed the default window for signals without filters.

**Fix**
- **`src/dispatch/signal/service.py`:** `_window_start` now takes minutes. The default no-filter window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, with no `* 60`, so it is still 45 minutes. Per-filter windows are read as minutes again.
- **`src/dispatch/signal/models.py`:** the column default is now 60 (it was 3600 with a "seconds" comment) and the pydantic default is now 10 (it was 600). Both still mean 1 hour and 10 minutes, but now in minutes.
- **Existing filters:** I didn't add a migration. Rows saved through the UI hold 5–30 and work as they are. The one thing I haven't checked is rows that were never set through the UI. A row that holds the old column default of 3600 would now mean 3600 minutes (about 60 days), and the old pydantic default of 600 would mean 10 hours. Querying for `window > 30` would show whether any exist.

**Test**
I added `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It creates an instance with a case dated ten minutes ago, then a second instance with the same entity under a filter with `window=30`. It asserts the second instance is deduplicated into the first one's case.

The new test fails with the source changes stashed and passes with them. All of `tests/signal/test_signal_service.py` passes: 15 passed, 1 skipped.

----- next turn -----

The cause is `086dc910` (2025-08-07, "simplify snooze filter checks"). It's the same batch of changes as the dedup bug, but a different commit.

In `filter_snooze`, the old code did `continue` when it hit an expired snooze filter, so it moved on to the next filter. The refactor changed that to `break`, which ends the whole loop. For "Okta: Impossible travel", the expired filter from last week came first, so the loop stopped there. The valid filter that runs until next month was never checked, and new instances for that user weren't snoozed. The commit message says nothing about this change, and it only shows up if a signal has more than one snooze filter and an expired one comes first.

**Fix:** I changed the `break` back to `continue` in `src/dispatch/signal/service.py`. The `break` after a successful snooze match stays, since there's nothing more to check once a filter matches.

**Test:** I added `test_filter_actions_snooze_expired_filter_does_not_mask_active_one` in `tests/signal/test_signal_service.py`. It gives a signal an expired snooze filter (7 days ago) listed before a valid one (30 days ahead), both matching the same entity, and asserts the instance is snoozed. It fails without the fix and passes with it. All of `tests/signal` passes: 34 passed, 1 skipped.

My first attempt at the fail-without-fix check selected no tests because I used the wrong `-k` name. I reran it with the correct name and got the failure shown above.

Nothing is committed. The working tree now holds both fixes (dedup window and snooze), and the changes are in `service.py`, `models.py` and the test file.

----- next turn -----

## Recap

Two regressions came from refactors made in August 2025. Both are fixed in the working tree and not yet committed.

- **Dedup windows:** `917a0b7b` made `SignalFilter.window` be read as seconds. The UI offers 5–30 and stores them as minutes, so a 30-minute window became 30 seconds and related instances opened separate cases. `_window_start` in `src/dispatch/signal/service.py` now takes minutes. The column and pydantic defaults in `models.py` were changed to 60 and 10 so they still mean 1 hour and 10 minutes. No migration is needed for rows saved through the UI. Rows that were never set through the UI and still hold the old default values (3600 or 600) would now be read as minutes and become very long windows, so check for those before release.
- **Snooze:** `086dc910` changed `continue` to `break` for expired snooze filters. An expired filter listed first then stopped the loop, so a valid filter after it never applied. It is back to `continue`.
- **Canary:** `a348bbd2` made canary instances skip deduplication and excluded existing canary instances from dedup matching.
- **Default window:** `7a9fe810` made the window for signals without filters configurable. It changed from a fixed 1 hour to 45 minutes by default.
- **Tests:** each regression has a test that fails without its fix and passes with it. `tests/signal` shows 34 passed and 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES