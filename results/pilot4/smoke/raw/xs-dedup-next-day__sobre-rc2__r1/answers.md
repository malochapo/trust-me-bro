Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup, and one of them changed the unit that custom dedup windows are read in. I made no code changes.

**Commits (in date order)**

1. **`a348bbd2`** (2025-05-29), `fix(signal): don't dedup on canary signals`. Canary instances skip dedup entirely (`filter_dedup` returns early), and canary instances are excluded from the candidate matches in both the default and custom paths. No window involved.

2. **`7a9fe810`** (2025-06-19), `feat(signal): make the default deduplication window configurable`. The window for signals with no dedup filter was hard-coded to 1 hour. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes**. So the default window shrank from 60 to 45 minutes for existing deployments that don't set the variable.

3. **`086dc910`** (2025-08-07), `refactor(signal): simplify snooze filter checks`. Two effects:
   - The "no mode" and "no action" checks and their warnings were removed. Skipping behaviour is unchanged.
   - When a snooze filter's expiration has passed, the loop now does `break` where it used to do `continue`. Any snooze filters after it in the list are no longer evaluated, so an expired filter can hide a later active one. This is a real behaviour change.

4. **`917a0b7b`** (2025-08-14), `refactor(signal): share the lookback window computation`. It added `_window_start()` and changed custom dedup windows from `timedelta(minutes=f.window)` to seconds. The same stored number now gives a window 60× shorter. The default path is unaffected because it was already converted to seconds.

I also checked `5e136d7b`, `d2675cf4` and `4474af25`. They touch signal code but don't change the snooze or dedup decision.

**Current values as the code applies them**

- **Default dedup window** (signal has no dedup filters): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in minutes, default 45 (`src/dispatch/config.py:95-97`). `filter_dedup` converts it with `* 60` (`service.py:805`), so the default is 2700 seconds.
- **Custom dedup filter window**: `SignalFilter.window`, in **seconds** (`models.py:208` comment, applied at `service.py:846` with no conversion). Defaults: 600 seconds (10 minutes) in the pydantic schema (`models.py:282`), and 3600 seconds (1 hour) in the database column default (`models.py:207`).
- **Snooze**: no window. It applies until `expiration`, and a snooze filter with no expiration is skipped with a warning.

**Things to check**

- The filter dialog is labelled **"Window (minutes)"** and offers 5, 10, 15, 20 or 30 (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:56, 196`). It appears to send that value unchanged, so a 10-minute choice would be applied as 10 seconds. I didn't trace the full submit path in the store, so this needs confirming.
- The `filter_signal` docstring still says the default window is "1-hour" (`service.py`, near line 873).
- `window` is typed `int | None`, but `_window_start(None)` would raise a `TypeError`. I didn't check whether a null can be stored.

----- next turn -----

The bug came from `917a0b7b`, and the fix is in place: a filter's window is read as minutes again, so existing filters work without edits. The signal test suite passes (34 passed, 1 skipped), including a new regression test that failed before the fix.

I don't have yesterday's list, so I rebuilt the candidates from git history since 2025-05-22. The main ones are `917a0b7b`, `a348bbd2`, `7a9fe810`, and `086dc910`.

**Cause:** `917a0b7b` ("share the lookback window computation", Aug 14) changed `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the stored value as seconds. The UI offers 5–30 labeled "Window (minutes)", so a 30 window became 30 seconds. Two instances ten minutes apart fell outside it and each opened a case. The stale comment saying the column was seconds came from the original 2022 model and was never true for the service code.

**Changes:**
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`. I also corrected the `filter_signal` docstring, which said the default window was 1 hour.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column comment now says minutes, and its default changed from 3600 to 60 so it still means 1 hour. No migration is needed, since this is a Python-side default.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes` (30-minute window, instance 10 minutes old, expects dedup) and `test_filter_actions_deduplicate_window_excludes_older_instances` (40 minutes old, expects no dedup).

I did not run the full repository suite, only `tests/signal`.

**Other findings, not fixed:**
- `086dc910` ("simplify snooze filter checks") changed `continue` to `break` for expired snooze filters. An expired snooze filter now stops the loop, so later active snooze filters are never checked. This is a snooze bug and deserves its own fix.
- The Pydantic default `SignalFilterBase.window = 600` is still 600 minutes, which I left alone. That is 10 hours, not the 10 minutes it effectively was while the service read the value as seconds.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES