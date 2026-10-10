New instances for that user are snoozed again, as long as one of their snooze filters is still valid. The signal tests pass with the fix, and the new regression test fails without it.

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py`), an expired filter hit a `break`. That stopped the loop, so any valid filter later in the list was never checked. If the expired filter came first, the user was never snoozed. A single filter, or an expired filter placed after the valid one, would have hidden the bug. That fits "worked before the second filter was added".

**Fix:** I changed `break` to `continue`, so expired filters are skipped and the rest still get checked.

**Test:** `test_filter_actions_snooze_expired_and_valid` in `tests/signal/test_signal_service.py`. It gives a signal two snooze filters for the same entity, one expired and one valid, with the expired one first. It asserts that the instance ends up snoozed.

I only ran `tests/signal/test_signal_service.py` (15 passed, 1 skipped), not the full suite.