Five commits since 2025-05-22 changed snooze or dedup decisions or their windows. I didn't change any code.

| Commit | Date | What changed |
|---|---|---|
| `a348bbd2` | 2025-05-29 | **Canary signals are excluded from dedup.** Canary instances skip `filter_dedup` entirely, and canary instances are no longer matched as dedup targets, in both the default path and the per-filter path. No window involved. |
| `7a9fe810` | 2025-06-19 | **The default dedup window moved from a hardcoded 1 hour to a config value.** It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (env var, default `45`). The commit message says "configurable", but the default also dropped from 60 to 45 minutes, so the effective default changed. |
| `086dc910` | 2025-08-07 | **Snooze checks simplified, with one behavior change.** The mode and action checks are merged into one condition, and the "no mode" and "no action" warnings are gone. An expired snooze filter now `break`s out of the loop instead of `continue`-ing, so later active snooze filters on the same signal are no longer evaluated. |
| `917a0b7b` | 2025-08-14 | **Per-filter dedup window changed from minutes to seconds.** The old code was `timedelta(minutes=f.window)`; it is now `_window_start(f.window)`, which treats the value as seconds. A stored window of 600 used to mean 600 minutes and now means 600 seconds. The commit also added the `_window_start` helper and made the default window `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. |

`4474af25` (2025-06-10) only logs the outcome of each processed instance, so it doesn't change decisions. `d2675cf4` and `5e136d7b` don't touch snooze or dedup logic.

**Current values as the code applies them:**
- **Snooze:** no time window. A snooze filter is active until its `expiration` datetime, and it matches by `expression` (or all instances if there is no expression). Snooze is checked first, and dedup runs only if the instance was not snoozed.
- **Default dedup (signals with no filters):** 45 minutes, which is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` = 2700 seconds, measured back from now against `created_at`. It matches the most recent instance with a case, and canaries are excluded.
- **Per-filter dedup window:** seconds. The API schema default (`SignalFilterBase.window`) is 600 seconds (10 minutes). The DB column default (`SignalFilter.window`) is 3600 seconds (60 minutes). Neither default has changed since the cutoff.

**Things to check:**
- `917a0b7b` changed the units of existing per-filter windows without any migration in these commits. I didn't check the database migrations, so I can't confirm whether stored values were converted. If they weren't, existing filters now dedup over a window roughly 60 times shorter than before.
- The `filter_signal` docstring still says the default dedup is a "1-hour window", which no longer matches the 45-minute default.

----- next turn -----

The bug came from `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the per-filter window from minutes to seconds, so a filter set to 30 in the UI only looked back 30 seconds. The fix is in place and the regression tests pass. Nothing is committed.

**Cause:** The UI's "Window (minutes)" field (options 5–30) stores minutes. Before `917a0b7b`, the code read it as minutes. After it, the code read it as seconds. Your two instances were ten minutes apart (600 seconds), which is outside a 30-second window, so they opened two cases.

**Fix:**
- `src/dispatch/signal/service.py`: `filter_dedup` now computes the window as `_window_start(f.window * 60)`. Existing filters work without edits. A stored 30 means 30 minutes again, which is what it meant before `917a0b7b`.
- `src/dispatch/signal/service.py`: the `filter_signal` docstring said "1-hour window" for the default dedup. It now says 45 minutes.
- `src/dispatch/signal/models.py`: the column comment said seconds and mentioned a 1-hour default. It now says minutes.

**Regression tests** in `tests/signal/test_signal_service.py`:
- `test_filter_actions_deduplicate_window_is_minutes`: an earlier instance 10 minutes old with window 30 must deduplicate. It failed before the fix and passes now.
- `test_filter_actions_deduplicate_outside_window_minutes`: an instance 40 minutes old with window 30 must not deduplicate. This guards against the window being read as too large.

**Test results:**
- `tests/signal`: 34 passed, 1 skipped.
- Full suite: 361 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They fail the same way with my changes stashed, so they predate this fix. I didn't investigate them.

**Left unchanged, for you to decide:**
- The model defaults are still `SignalFilterBase.window = 600` and the column default `window = 3600`. Under the minutes meaning, those are 10 hours and 60 hours if an API caller omits `window`. The UI always sends a value, so I didn't change them, since that alters behavior for API callers.
- `086dc910` also changed an expired snooze filter from `continue` to `break`. Later active snooze filters on the same signal are now skipped. That's a separate question from this bug, so I didn't touch it.

----- next turn -----

The cause was `086dc910` (2025-08-07, "simplify snooze filter checks"). In `filter_snooze`, it changed the expired-filter branch from `continue` to `break`. Any expired snooze filter listed before a valid one stopped the loop, so the valid filter was never checked. That's why the Okta user's new instances were not snoozed.

**Fix** (`src/dispatch/signal/service.py`): the expired-filter branch uses `continue` again, so the loop moves on to the next filter. Nothing else in the snooze logic changed.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_expired_then_valid` puts an expired snooze filter first and a valid one for the same entity second, then asserts the instance is snoozed. It fails on the old code and passes with the fix.

**Results:**
- `tests/signal`: 35 passed, 1 skipped.
- Full suite: 362 passed, 4 skipped, 8 failed. The same 8 failures as before (in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`) also fail on the original code, so they predate these changes.

Nothing is committed. The `086dc910` change was a refactor that dropped the `break`/`continue` distinction; this fix reverts only that line.

----- next turn -----

Recap of this session's changes (all uncommitted in the working tree):

- **Deduplication windows (`917a0b7b`)**: per-filter dedup windows were read as seconds instead of minutes, so a filter set to 30 in the UI covered 30 seconds. Fixed in `filter_dedup` to multiply by 60. Existing filters need no edits. Regression tests: `test_filter_actions_deduplicate_window_is_minutes` and `test_filter_actions_deduplicate_outside_window_minutes`.
- **Snoozing (`086dc910`)**: an expired snooze filter stopped the loop with `break`, so a valid snooze filter listed after it was never checked. Changed back to `continue`. Regression test: `test_filter_actions_snooze_expired_then_valid`.
- **Docs**: the `filter_signal` docstring and the `SignalFilter.window` column comment now describe the default and the window in the right units.
- **Test status**: `tests/signal` passes (35 passed, 1 skipped). The full suite has 8 failures in `tests/ai`, `tests/database`, and `tests/entity` that also fail on the original code.
- **Not changed**: the API default `SignalFilterBase.window = 600` and column default `3600` are still in the old numbers, which now mean 10 hours and 60 hours if omitted. `7a9fe810` also dropped the default dedup window from 60 to 45 minutes when it made the value configurable.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES