Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup, and one of them changed the units of the filter dedup window. I made no code changes.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals". Canary signal instances skip dedup entirely, and canary instances are excluded as dedup candidates in both the default and filter-based paths. No time window involved.

2. **`7a9fe810`** (2025-06-19), "feat(signal): make the default deduplication window configurable". The default window for signals with no dedup filter was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`config.py:95`), which defaults to 45 minutes.

3. **`086dc910`** (2025-08-07), "refactor(signal): simplify snooze filter checks". Two behavior changes in `filter_snooze`:
   - An expired snooze filter now `break`s out of the loop instead of `continue`, so later snooze filters on that signal are no longer evaluated.
   - The warnings for filters with no mode or no action were removed. Those filters are now skipped silently.
   
   No window values involved.

4. **`917a0b7b`** (2025-08-14), "refactor(signal): share the lookback window computation". This added a `_window_start(seconds)` helper. The default path now computes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is the same 45 minutes as before. The filter dedup path changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, so `f.window` is now read as **seconds**. The commit title doesn't mention this, but the diff does, and it makes filter windows 60× shorter than before for existing rules. Please confirm that's intended.

**Windows and values as the code applies them today**

- **Snooze:** no lookback window. A snooze applies until the filter's `expiration` datetime passes. A snooze filter with no expiration is skipped with a warning.
- **Default dedup (signal has no filters):** 2700 seconds (45 minutes), counted back from now on `created_at`. Matches only instances on the same signal that have a `case_id`, aren't canary, and aren't the instance itself.
- **Filter dedup (signal has a dedup filter):** `SignalFilter.window` in seconds, used as-is. The stored default is 3600 seconds (column default in `signal/models.py:206`). The API schema default is 600 seconds (`signal/models.py:282`).

**Stale documentation**

- The `filter_signal` docstring still says the default dedup window is 1 hour.
- The `window` column comment says the default is 1 hour, which doesn't match the 45-minute default for filterless signals.

**Checked and excluded**

- `4474af25` (logging) and `d2675cf4` (redaction) touch `flows.py` but don't change snooze or dedup decisions.
- The 5-second check in `flows.py:373` predates the window and controls thread updates, not snooze or dedup.
- `200cd428`, `907bc4b6`, and `5e136d7b` matched my search terms but don't change snooze or dedup logic.

----- next turn -----

The cause was `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It started reading a filter's `window` as seconds. The UI labels that field "Window (minutes)" and sends the raw number, so a stored 30 means 30 minutes. Under the seconds reading, the window was 30 seconds, so two instances ten minutes apart never grouped.

**Fix** (`src/dispatch/signal/service.py`)
- The filter dedup path now reads `f.window` as minutes: `_window_start(f.window * 60)`.
- Existing filters need no edits. Their stored values already mean minutes, as the UI intends.
- The default path (no filters, 45 minutes via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) is unchanged.
- I corrected the stale comment on `SignalFilter.window` in `src/dispatch/signal/models.py` to say minutes.

**Regression tests** (`tests/signal/test_signal_service.py`)
- `test_filter_actions_deduplicate_window_is_minutes`: a window of 30 groups an instance with one created 10 minutes earlier. It failed on the current code and passes now.
- `test_filter_actions_deduplicate_window_expired_is_minutes`: an instance 40 minutes earlier is not grouped. It passes both before and after, so it guards the lower bound.

**Test results**
- `tests/signal`: 34 passed, 1 skipped.
- Full suite: 361 passed, 4 skipped, 8 failed. The same 8 fail with my changes stashed. They are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I didn't investigate them.

**Things you should decide**
- **Model defaults:** the column default is still `60 * 60`, which is now 3600 minutes, and the API schema default is 600 minutes. I left them alone because changing them affects newly created filters. The UI's options are 5–30, so the column default looks wrong under the minutes meaning.
- **Filters created via the API since 2025-08-14:** if any were created with a seconds value, their windows are now 60× too long. I can't tell which filters those are from the code alone.

I haven't committed anything.

----- next turn -----

The cause was `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). It changed the expired-filter branch in `filter_snooze` from `continue` to `break`. When an expired snooze filter came first in the signal's filter list, the loop stopped, so the valid one was never checked. New instances for that user then weren't snoozed.

**Fix** (`src/dispatch/signal/service.py`): the expired branch is back to `continue`, so the loop moves on to the other filters. Filter order no longer changes the result.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_expired_then_valid` gives a signal an expired snooze filter (expired 7 days ago) followed by a valid one (expires in 30 days), then checks that a new instance for the same entity is snoozed. It failed before the fix and passes now.

**Test results**
- `tests/signal`: 35 passed, 1 skipped.
- Full suite: 362 passed, 4 skipped, 8 failed. The 8 failures are the same ones as before (AI service, restricted case filter, entity field-only), so they predate this change.

I haven't committed anything.

----- next turn -----

Here's the recap of this session's work, followed by the changelog lines.

**Summary**

- **Deduplication windows (`917a0b7b`):** the refactor read a filter's `window` as seconds, but the UI sets it in minutes. Filters grouped only over the window in seconds, so a 30-minute window matched only 30 seconds. Fixed in `signal/service.py` by reading `f.window` as minutes. Existing filters work without edits. Added `test_filter_actions_deduplicate_window_is_minutes` and `test_filter_actions_deduplicate_window_expired_is_minutes`.
- **Snoozing (`086dc910`):** an expired snooze filter ended the loop with `break`, so a valid snooze filter later in the list was never checked. Fixed by changing it back to `continue`. Added `test_filter_actions_snooze_expired_then_valid`.
- **Canary signals (`a348bbd2`):** not changed in this session. I only report it here.
- **Tests:** `tests/signal` passes (35 passed, 1 skipped). The full suite has 8 failures that also occur without these changes: 6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`.
- **Open items:** the `SignalFilter.window` column default is still 3600 and the API schema default is 600, both now read as minutes. Filters created through the API with seconds values since 2025-08-14 are now 60× too long. Neither is changed, and I haven't committed anything.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES