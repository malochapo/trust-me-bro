The bug is fixed. An expired snooze filter no longer stops the check from reaching a valid one. The new test fails without the fix, and with it all 15 tests in `tests/signal/test_signal_service.py` pass (1 skipped).

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py`), the check for an expired filter used `break`. That ended the loop at the first expired filter, so any valid snooze filter after it was never checked. The loop's order depends on how the signal's filters are stored. With the old expired filter ahead of the new one, snoozing stopped working once the second filter was added. I changed `break` to `continue`.

**Test:** I added `test_filter_actions_snooze_expired_and_valid` in `tests/signal/test_signal_service.py`. It gives a signal two snooze filters with the same expression, one expired 7 days ago and one valid for 30 more days, with the expired one first. It then checks that the instance ends up snoozed.

I haven't committed anything.