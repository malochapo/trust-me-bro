Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or the windows it uses. All of them are in `src/dispatch/signal/service.py`, and I made no code changes.

1. **`a348bbd2`** (2025-05-29, "don't dedup on canary signals"): canary signals skip deduplication entirely, and canary instances are excluded as dedup candidates. No window involved.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable"): the window for signals with no dedup filter moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py`, default 45). Today that is 45 minutes, or 2700 seconds.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks"): in `filter_snooze`, an expired snooze filter used to `continue` to the next filter. It now `break`s out of the loop, so later snooze filters are no longer checked once an expired one is hit. This is a behaviour change, not just a refactor.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation"): the per-filter dedup window (`SignalFilter.window`) is now read as **seconds**. Before, it was `timedelta(minutes=f.window)`. The commit adds `_window_start()`, which takes seconds, and the default window is now passed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`.
   - Current values: the pydantic schema default is 600 seconds (10 minutes), and the model column default is 3600 seconds (1 hour).
   - Problem: the commit changed the unit without changing stored values, and I found no data migration for it. Existing filters with a `window` value now look back 60 times less far than before. I did not check the migrations directory in depth, so this is unverified beyond the absence of a migration in my search.

Two things I did not count as decision changes:
- `timedelta(seconds=5)` in `flows.py` throttles Slack message updates, not the dedup decision.
- `4474af25` only adds logging.

Also, the comment in `tests/signal/test_signal_service.py` (around line 396) still says "1-hour window", which no longer matches the 45-minute default.

I saved these findings to the memory directory for future sessions.

----- next turn -----

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