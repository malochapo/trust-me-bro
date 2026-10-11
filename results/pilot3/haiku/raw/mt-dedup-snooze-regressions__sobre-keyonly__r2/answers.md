I found four commits since 2025-05-22 that changed the snooze or dedup decision, and one of them changed the window units. I made no code changes.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29, "don't dedup on canary signals"). Canary signal instances are no longer deduplicated. The default path and the filter path both skip them, and canary instances are excluded as dedup candidates. No window changed.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable"). For a signal with no dedup filters, the window was hard-coded at 1 hour. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks"). Two behaviour changes:
   - An expired snooze filter used to be skipped with `continue`, so later snooze filters on the signal were still checked. It now uses `break`, which stops evaluation, so a single expired snooze filter now prevents any later snooze filters from applying.
   - The warnings for filters with no mode or no action were removed. Those filters are now skipped silently.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation"). This changed the window units and shared the calculation in a new `_window_start(seconds)` helper:
   - A filter's `window` used to be applied as minutes (`timedelta(minutes=f.window)`). It is now applied as seconds.
   - The default 45-minute window is converted with `* 60` before being passed in, so its effective length is unchanged.
   - This commit changed only `service.py`, with no data migration. If existing filter windows were entered as minutes, they now apply 60× shorter.

**Current values as the code applies them**

- **Snooze:** no window. A snooze filter applies while its `expiration` is in the future. Filters with no expiration are skipped with a warning.
- **Per-filter dedup window:** `SignalFilter.window` is in seconds. The database column defaults to 3600 (1 hour). The Pydantic `SignalFilterBase` defaults to 600 (10 minutes).
- **Default dedup window (signal has no filters):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes, which is 2700 seconds after conversion.

**Stale documentation:** the `filter_signal` docstring still says the default grouping is a "1-hour window", but the code uses 45 minutes by default.

**Not included:** `4474af25` (logs signal outcomes), `5e136d7b` (UI), `d2675cf4` (redaction config), and `90f73fe2` (stats). None of them change the snooze or dedup decision.

**Not verified:** I searched the frontend for the filter window input but did not find it, so I could not confirm which unit the UI sends when a user sets a window.

----- next turn -----

The window is back to meaning minutes. The cause was `917a0b7b`, which started reading `SignalFilter.window` as seconds. That is why the 30 in the UI became a 30-second window, so two instances ten minutes apart opened two cases. None of the other commits I listed caused it.

**Why I'm sure:** the UI's "Window (minutes)" dropdown offers 5, 10, 15, 20, or 30, and sends the raw value. Existing rows therefore already hold minutes, so reverting the interpretation means no filter needs editing.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The per-filter window and the default window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, no `* 60`) both use it. I also fixed the `filter_signal` docstring, which still said "1-hour window".
- `src/dispatch/signal/models.py`: the column comment now says minutes.
- `tests/signal/test_signal_service.py`: added `test_filter_window_is_in_minutes`, parametrized over two cases. A 30-minute window deduplicates an instance 10 minutes earlier, and does not deduplicate one 40 minutes earlier. Added `import pytest` at the top of the file for the parametrize decorator.

**Verification**
- Before the fix, the 10-minute case failed with `'none' == 'deduplicate'`. The 40-minute case passed.
- After the fix, `tests/signal` gives 34 passed, 1 skipped.
- Full suite: 361 passed, 4 skipped, 8 failed. The same 8 fail on the untouched tree (7 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`), so they predate this change.
- `ruff check` passes on the changed files. `ruff format` flags a blank line in `models.py` near the bottom of the file, which predates my change, so I left it alone.

**Left as-is, for you to decide**
- The numeric defaults are unchanged. `SignalFilter.window` defaults to 3600 in the column, which is now 60 hours, and the API schema defaults to 600, which is 10 hours. Both were applied as minutes before the regression too. The UI always sends an explicit value, so this only affects filters created without one. Should I change them to 60 and 10?
- `086dc910`'s change from `continue` to `break` on expired snooze filters is unrelated to this bug. I didn't touch it.

Nothing is committed.

----- next turn -----

The cause was `086dc910`, the snooze simplification I flagged earlier. It changed the expired-filter branch in `filter_snooze` from `continue` to `break`. An expired snooze filter now ends the loop, so any valid snooze filter after it is never checked. That's why the "Okta: Impossible travel" instances for that user weren't snoozed.

**Fix:** `src/dispatch/signal/service.py` now uses `continue` for expired snooze filters, so the loop moves on to the next filter. This restores the behaviour from before `086dc910`.

**Regression test:** `test_filter_actions_snooze_after_expired_snooze` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter (7 days ago) and a valid one (30 days ahead), both matching the same entity, with the expired one evaluated first. The instance must be snoozed. Before the fix it failed with `assert False`. After the fix it passes.

**Verification**
- `tests/signal`: 35 passed, 1 skipped.
- `ruff check` on the signal code and tests: clean.
- Full suite: 362 passed, 4 skipped, 8 failed. The same 8 failures exist on the untouched tree (in `tests/ai/test_ai_service.py` and two other tests), so they predate these changes.

Nothing is committed.

----- next turn -----

Here's the recap. None of the fixes is committed yet. The working tree has the changes in `src/dispatch/signal/service.py`, `src/dispatch/signal/models.py`, and `tests/signal/test_signal_service.py`.

- **Dedup windows:** `917a0b7b` started reading `SignalFilter.window` as seconds, although the UI sends minutes. A 30-minute window became 30 seconds. The fix reads it as minutes again, with a regression test in `test_filter_window_is_in_minutes`.
- **Snoozing:** `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze filter after an expired one was never checked. The fix restores `continue`, with a regression test in `test_filter_actions_snooze_after_expired_snooze`.
- **Canary signals:** `a348bbd2` stopped canary instances from being deduplicated and from counting as dedup candidates. It is the intended behaviour, so I didn't change it.
- **Default window:** signals with no filter are grouped over 45 minutes. The value is set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which can be overridden through the environment.

Tests: `tests/signal` passes (35 passed, 1 skipped). The full suite has 8 failures that predate these changes, in `tests/ai/test_ai_service.py` and two other tests.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES