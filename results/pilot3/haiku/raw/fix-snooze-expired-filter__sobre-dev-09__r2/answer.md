Fixed. An expired snooze filter was ending the whole filter loop, so a valid snooze filter listed after it was never checked.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`, around line 763), an expired filter hit `break`. That exits the loop over `signal_instance.signal.filters`, so the still-valid snooze for the same user was never evaluated. New instances then fell through to case creation.

**Fix:** Changed that `break` to `continue`, so an expired filter is skipped and the remaining filters are still checked. The other `break` in the function, the one that fires after a snooze actually matches, is unchanged.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter, then a valid one for the same entity, and asserts the instance is snoozed. I confirmed it fails with the old code and passes with the fix.

**Test results:** `python -m pytest tests/signal` gives 33 passed, 1 skipped.

I didn't commit anything. Only the signal filter path was touched, so the Slack snooze modal and stats code were not re-run.