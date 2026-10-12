Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or the windows it uses. I made no code changes.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29, "fix(signal): don't dedup on canary signals", #6026)
   - Dedup now returns early for canary instances, and canary instances are excluded from the candidate matches in both the default-window and filter-window queries.
   - No window values changed.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable")
   - The default dedup window for signals with no dedup filter was `timedelta(hours=1)`. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` from `src/dispatch/config.py`, default `45`, in minutes.

3. **`086dc910`** (2025-08-07, "refactor(signal): simplify snooze filter checks")
   - Merged the mode/action checks into one condition. The log warnings for missing mode and action were dropped.
   - Behaviour change: in `filter_snooze`, an expired snooze filter used to `continue` to the next filter. It now `break`s out of the loop, so any active snooze filters after an expired one are no longer checked.

4. **`917a0b7b`** (2025-08-14, "refactor(signal): share the lookback window computation")
   - Added `_window_start(seconds)` and routed both windows through it.
   - Behaviour change, despite the "refactor" label: the per-filter window was `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats `f.window` as seconds. That matches the model comment and column default (`signal/models.py:206`, "number of seconds… default to 1 hour"), but it makes filter dedup windows 60× shorter than before for existing filters.
   - The default dedup window is unchanged in effect: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, so still 45 minutes.

**Windows as the code applies them today**

| Window | Value | Unit | Where |
|---|---|---|---|
| Default dedup (signals with no dedup filter) | 45 | minutes (env `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, converted to 2700 s) | `config.py:95`, `service.py:805` |
| Per-filter dedup `SignalFilter.window` | model default 3600 | seconds (1 hour) | `signal/models.py:206` |
| Per-filter dedup API schema default | 600 | seconds (10 minutes) | `signal/models.py:282` |
| Snooze | none | snooze uses `SignalFilter.expiration` (a datetime), not a window | `service.py:743` |

The 600 default in the API schema is worth a look: it is 10 minutes, while the column default is one hour.

Commits that only touched the UI or unrelated signal code (`5e136d7b`, `90f73fe2`, `dee1699d`) were excluded. I recorded the findings in the sobre session.

----- next turn -----

I saved the work in the sobre session, so tomorrow's session can pick it up with `sobre_session` `action="load"`. I did not write a memory file, because the commit history itself holds the facts and a memory would only duplicate it.

What's recorded:
- **Finding:** the four commits since 2025-05-22 (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`) and the current windows: default dedup 45 minutes, per-filter `SignalFilter.window` in seconds, snooze driven by `expiration` only.
- **Task:** follow up on `917a0b7b`, which changed the per-filter dedup window from minutes to seconds without a behaviour-change label, shortening existing windows 60×. Confirm the intent with the author (Jordan Lee) and check whether existing filter rows were migrated. Also review `086dc910`'s `continue`→`break` change in the expired-snooze path, and the mismatch between the API schema default (600 s) and the column default (3600 s).
- **Decision:** this was a read-only review, and no code was changed.

Nothing is pending. The next step is the follow-up task above.

----- next turn -----

The window bug came from `917a0b7b` ("refactor(signal): share the lookback window computation"). It changed how `filter_dedup` reads a filter's window, so a window of 30 now means 30 seconds. The UI writes minutes (5–30), so the stored value was never seconds.

**Root cause**
- Before `917a0b7b`, `filter_dedup` used `timedelta(minutes=f.window)`, which matched the UI.
- The refactor moved the calculation into `_window_start(seconds)` and passed `f.window` straight through, with a comment saying the field was in seconds. The model comment was wrong too; it said seconds.
- Your two GuardDuty instances ten minutes apart fall outside a 30-second window, so they opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. Both the per-filter window and the default window pass minutes. Existing filters need no edits, because stored values are already minutes.
- `src/dispatch/signal/models.py`: corrected the column comment to minutes. I also changed the column default and the `SignalFilterBase.window` default from 3600 and 600 to 60, so they mean one hour in the right unit. This changes what an API caller gets if they omit `window`. Say if you'd rather I leave those defaults alone.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes`. A sibling 10 minutes earlier, in its own case, must be matched by a 30-minute window. A sibling 40 minutes earlier must not. The test fails without the fix and passes with it.

**Verification**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- Full `python -m pytest`: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail identically on the untouched tree, so they predate this change and I did not touch them.

**Other findings**
- The default window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. It was introduced in `7a9fe810`, replacing a hard-coded 1 hour.
- `a348bbd2` ("don't dedup on canary signals") is the canary change.
- `086dc910` changed `continue` to `break` for expired snoozes in `filter_snooze`. That looks like a separate snooze bug, since it stops checking later snooze filters. I didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES