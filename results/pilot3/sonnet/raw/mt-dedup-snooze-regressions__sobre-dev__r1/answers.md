Three commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated, plus a fourth that changed the snooze check's behavior while presenting itself as a refactor. I read the code and diffs and changed nothing.

**Commits that changed the behavior**

- **`a348bbd2` (2025-05-29), "don't dedup on canary signals".**
  - `filter_dedup` now returns early when the incoming instance is a canary.
  - Canary instances are also excluded from the lookback queries, in both the default path and the per-filter path.
  - It doesn't change any window.
- **`7a9fe810` (2025-06-19), "make the default deduplication window configurable".**
  - The default window used for signals with no filters was a hard-coded `timedelta(hours=1)`.
  - It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` from `config.py`, which defaults to **45 minutes**.
  - Signals with no filters therefore went from 1 hour to 45 minutes, unless the setting is overridden.
- **`917a0b7b` (2025-08-14), "share the lookback window computation".**
  - This looks like a pure refactor, but it changed the per-filter window's unit.
  - It added `_window_start(seconds)`.
  - Before it, a filter's dedup window was `timedelta(minutes=f.window)`.
  - After it, it is `_window_start(f.window)`, which means seconds.
  - The default window is now `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes.
- **`086dc910` (2025-08-07), "simplify snooze filter checks".**
  - It removed the warnings for a missing mode or action and merged those checks into one condition.
  - It also changed an expired snooze filter from `continue` to `break`.
  - Once the loop reaches an active snooze filter whose expiration has passed, it stops checking any later snooze filters, so a later unexpired snooze filter no longer snoozes the instance.

**Windows as the code applies them today**

- **Default dedup window** (signal has no filters at all): 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` and multiplied by 60 into seconds.
  - It matches the latest earlier instance of the same signal that has a case and isn't a canary.
- **Per-filter dedup window** (active deduplicate filters): `SignalFilter.window` is read as **seconds**.
  - The column default is `60 * 60`, which is 1 hour.
  - The Pydantic schema default is 600, which is 10 minutes.
- **Snooze:** there is no lookback window. It depends only on the filter's `expiration` timestamp being in the future.

**Stale or inconsistent bits**

- The `filter_signal` docstring still says the default is a "1-hour window", which is now wrong.
- The per-filter window is now read as seconds. The column comment and default (`60 * 60`) already say seconds. If any stored values were written as minutes, they are now interpreted 60 times shorter. I didn't check for a data migration.
- Snooze always runs first. Dedup only runs if no snooze matched.

----- next turn -----

**Cause:** commit `917a0b7b` (2025-08-14, "share the lookback window computation"). It looked like a refactor, but it changed the per-filter window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which reads the value as seconds. Your filter's window of 30 became 30 seconds, so two instances ten minutes apart no longer matched and each opened its own case.

**Fix:** `src/dispatch/signal/service.py` now calls `_window_start(f.window * 60)`, with a comment that the window is stored in minutes. The UI labels the field "Window (minutes)" and offers 5, 10, 15, 20 and 30, so the stored values are minutes. Existing filters work again without being edited. The default 45-minute window for signals without filters was already correct and is unchanged.

**Test:** I added `test_filter_actions_deduplicate_window_is_in_minutes` to `tests/signal/test_signal_service.py`. It creates two instances for the same entity ten minutes apart and a deduplicate filter with `window=30`. It asserts the newer instance is deduplicated into the earlier one's case. It fails without the fix and passes with it. The whole file gives 15 passed and 1 skipped.

**Not changed:** the defaults and comments in `signal/models.py` still describe seconds.
- The `window` column default is `60 * 60`, with a comment saying "seconds … 1 hour". Read as minutes, that is 60 hours.
- The `SignalFilterBase` schema default is 600, which is 10 hours read as minutes.
- The UI always sends a value, so these only matter for filters created through the API without a window.

I'd set them to 60 and 10 and fix the comment, but that changes defaults for API-created filters, so I held off. Tell me if you want it.

----- next turn -----

**Cause:** commit `086dc910` (2025-08-07, "simplify snooze filter checks"). While merging the mode and action checks in `filter_snooze`, it also changed the expired-filter branch from `continue` to `break`. The loop therefore stops at the first expired snooze filter. If that filter is listed before the valid one, as in your "Okta: Impossible travel" case, the valid snooze is never checked. The instance then falls through to dedup and opens a case.

**Fix:** in `src/dispatch/signal/service.py`, an expired snooze filter now does `continue` again, so later filters are still evaluated.

**Test:** I added `test_filter_actions_snooze_skips_expired_filter` to `tests/signal/test_signal_service.py`. The signal has two snooze filters for the same entity, one expired a week ago and one valid for 30 more days, with the expired one first. The test asserts the instance is snoozed. It fails with the old `break` and passes now. The whole file gives 16 passed and 1 skipped.

My first version of the test failed because of a test-setup quirk, not the code. `SignalFilterFactory` commits the session, which expired the `signal.filters` collection and lost the pending append. The test now builds each filter before appending it, and a comment in the test says why.

The window fix from your previous request is also still uncommitted in the working tree.

----- next turn -----

**Recap**

- **Dedup windows:** commit `917a0b7b` (2025-08-14) was billed as a refactor but changed a filter's `window` from minutes to seconds. A window of 30 in the UI became 30 seconds. I fixed it in `signal/service.py` by multiplying the window by 60, and added `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozing:** commit `086dc910` (2025-08-07) changed `continue` to `break` on an expired snooze filter. An expired filter listed first stopped a later valid one from applying. I restored `continue` and added `test_filter_actions_snooze_skips_expired_filter`.
- **Canary signals:** commit `a348bbd2` (2025-05-29) made canary instances skip deduplication and excluded canaries from the dedup lookups.
- **Default window:** signals with no filters group over 45 minutes. Commit `7a9fe810` made this configurable, replacing a hard-coded 1 hour.
- **State:** the changes are uncommitted in the working tree. `tests/signal/test_signal_service.py` passes, with 16 passed and 1 skipped.
- **Left alone:** the `window` column default (`60 * 60`) and the schema default (600) in `signal/models.py` still describe seconds. The `filter_signal` docstring still says "1-hour" for the default window.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES