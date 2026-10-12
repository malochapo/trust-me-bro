**The cause is `917a0b7b`** (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the explicit-filter window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. The UI offers 5–30 labelled "Window (minutes)" and sends the number unchanged, so a 30-minute filter became a 30-second lookback. Two instances ten minutes apart fall outside that and open two cases. The commit title called it a refactor, but it was a unit change.

I ruled out the other candidates from the list:
- `086dc910` changed the expired-snooze branch from `continue` to `break`. That affects snooze, not the dedup window.
- `7a9fe810` only made the no-filter default configurable.
- `a348bbd2` is the canary change and does not touch the window.

**Fix** (uncommitted, in the working tree):
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`, so the stored value is minutes again. Existing UI filters store minutes, so they work without edits or a migration. I also corrected the `filter_signal` docstring, which said "1-hour window" when the default is 45 minutes.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default went from 3600 seconds to 60 minutes, and the comment now says minutes.
- `tests/signal/test_signal_service.py`: two new tests. `test_deduplicate_filter_window_is_in_minutes` puts an instance ten minutes old with a 30-minute filter and expects deduplication. `test_deduplicate_filter_window_expired` uses a 5-minute filter with the same setup and expects no deduplication.

**Verification:** the regression test fails on the pre-fix `service.py` and passes with the fix. `python -m pytest tests/signal tests/plugins/dispatch_slack/case` gives 43 passed, 1 skipped. I did not run the full suite.

**Choices to review:**
- I left the API schema default `window: int | None = 600` alone. Under minutes that is 10 hours, not the 10 minutes the code currently applies. Rows created through the API without a window since `917a0b7b` are ambiguous, so they may need a look.
- I did not commit.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES