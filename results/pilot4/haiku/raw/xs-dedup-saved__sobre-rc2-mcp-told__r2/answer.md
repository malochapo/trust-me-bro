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