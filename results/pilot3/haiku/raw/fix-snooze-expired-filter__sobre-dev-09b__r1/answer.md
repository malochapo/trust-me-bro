The snooze bug is fixed, and a regression test covers it.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter hit `break`, which exited the loop over the signal's filters. Any valid snooze filter listed after the expired one was never checked. For the Okta user, the expired filter was evaluated first, so new instances were not snoozed.

**Fix:** Changed that `break` to `continue`, so expired filters are skipped and evaluation moves on to the next filter.

**Regression test:** `test_filter_actions_snooze_expired_filter_does_not_mask_active_filter` in `tests/signal/test_signal_service.py`. It creates an expired filter (7 days ago) followed by an active one (30 days out), both matching the same entity, and asserts the instance is snoozed. I confirmed it fails with the old `break` and passes with the fix.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped.

The `signal.filters` relationship has no `order_by`, so the test depends on the database returning the expired filter first, the same way the bug is triggered in production. The existing snooze tests rely on the same behaviour.