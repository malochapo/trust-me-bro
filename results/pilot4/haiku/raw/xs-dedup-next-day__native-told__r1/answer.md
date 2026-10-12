The bug came from 917a0b7b, "refactor(signal): share the lookback window computation". It made per-filter windows read as seconds, but the UI and the stored values have always been minutes. A window of 30 became 30 seconds, so the two instances ten minutes apart never grouped. The fix makes the window mean minutes again, so existing filters work without edits. I did not commit the change.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start()` takes minutes. Both call sites pass minutes: the per-filter window and `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (the seconds conversion is gone).
- `src/dispatch/signal/models.py`: the column default is now `60` (still one hour), and the schema default is `10` (still the 10 minutes it effectively was). Both comments say minutes.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_minutes`. It has a case from ten minutes earlier and a window-30 filter, and expects deduplication. It failed before the fix and passes now. I also corrected a stale "1-hour window" comment to the 45-minute default.

**Verification**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- Full `python -m pytest`: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai`, `tests/database`, and `tests/entity`, and they fail the same way with my changes stashed, so they predate this work.
- `ruff check` passes on the changed signal files. The formatter's only complaint is in code I didn't touch.

**Things to know**
- I did not check production data. The fix assumes stored windows are minutes, which holds because the UI has always sent minutes.
- 086dc910 is a separate problem: `filter_snooze` now uses `break` on an expired snooze, so later snooze filters on the same signal are skipped. It isn't part of this fix; I left it alone.
- I updated my memory note on these commits to record the fix.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES