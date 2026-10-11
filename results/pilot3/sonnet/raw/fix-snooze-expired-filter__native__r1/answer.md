Fixed. In `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter ended the loop with `break`, so any valid filter after it was never checked. It now uses `continue`, so expired filters are skipped and the remaining ones are still evaluated.

I added a regression test, `test_filter_snooze__expired_filter_does_not_mask_valid_filter`, in `tests/signal/test_signal_service.py`. It gives a signal one expired and one valid snooze filter and checks that the instance gets snoozed. It fails without the fix and passes with it. The rest of `tests/signal/test_signal_service.py` still passes (15 passed, 1 skipped).

The test uses filters with an empty expression, so it covers the "snooze regardless of entity" path, not the case where an expression has to match the user.