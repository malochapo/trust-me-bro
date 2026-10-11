The snooze bug is fixed and a regression test covers it.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py:763`), an expired snooze filter hit `break`, which exited the loop over the signal's filters. Any valid snooze filter listed after the expired one was never checked, so new instances for that user were not snoozed. Before the second filter was added, the expired filter was the only one, so snoozing worked.

**Fix:** Changed that `break` to `continue`, so an expired filter is skipped and the loop moves on. This matches how the loop already treats inactive filters and non-matching expressions.

**Regression test:** `test_filter_actions_snooze_expired_before_active` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter and an active one (expiring in 30 days) for the same entity, lists the expired one first, and asserts the instance is snoozed. I confirmed it fails with the `break` restored and passes with the fix.

**Results:** `python -m pytest tests/signal` gives 33 passed, 1 skipped. I did not commit the changes.