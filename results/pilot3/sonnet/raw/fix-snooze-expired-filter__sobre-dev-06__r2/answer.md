Fixed. In `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter hit a `break`, which ended the loop. Any valid filter after it was never checked. I changed it to `continue`, so expired filters are skipped and the rest are still evaluated.

I added a regression test, `test_filter_snooze__expired_filter_does_not_mask_active_filter` in `tests/signal/test_signal_service.py`. It gives a signal one expired and one active snooze filter, and expects the instance to be snoozed. The test fails without the fix and passes with it. The rest of `tests/signal/test_signal_service.py` also passes (15 passed, 1 skipped).

The test uses filters with no expression, so it covers the expired-then-active ordering but not entity-matching expressions.