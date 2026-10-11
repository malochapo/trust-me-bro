Fixed. An expired snooze filter was ending the search for the whole signal, so a later valid filter for the same user was never checked.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py:763`), the expiration check used `break` when it found an expired filter. That exits the loop over the signal's filters, so any valid snooze filter after it was skipped. Snoozing worked before the second filter existed because there was only one filter to check.

**Fix:** Changed that `break` to `continue`, so an expired filter is skipped and evaluation moves on to the next one.

**Regression test:** Added `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter followed by an active one for the same entity, and asserts the instance is snoozed. I confirmed the test fails with the `break` restored and passes with the fix.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped. The one skip was already there and I did not change it.

Changes are uncommitted in the working tree.