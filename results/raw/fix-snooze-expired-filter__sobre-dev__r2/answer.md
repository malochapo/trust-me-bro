I fixed the bug in `filter_snooze` in `src/dispatch/signal/service.py`.

**Cause:** the loop over a signal's filters used `break` when it hit an expired snooze filter. That stopped it from checking any later filters. So when an expired filter came before the valid one, the valid one was never applied and the instance wasn't snoozed.

**Fix:** that `break` is now `continue`, so an expired filter is skipped and the remaining filters are still checked.

**Regression test:** `test_filter_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It gives a signal one expired and one valid snooze filter, in that order, and checks the instance ends up snoozed. It fails without the fix and passes with it, and the rest of `tests/signal` still passes (33 passed, 1 skipped).

The test's filters have no expression, so it covers the case where a snooze applies regardless of entity. I didn't add a separate test for filters that match on an entity such as the user. They go through the same loop, so the fix applies to them too.