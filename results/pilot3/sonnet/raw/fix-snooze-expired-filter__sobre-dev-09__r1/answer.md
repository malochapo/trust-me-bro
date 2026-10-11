I fixed the bug: an expired snooze filter no longer stops the remaining filters from being checked, so the valid one now snoozes the user's new instances again.

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py`), hitting an expired filter ran `break`, which ended the loop. If the expired filter came before the valid one, the valid one was never evaluated and the instance wasn't snoozed. I changed that `break` to `continue`.

**Regression test:** I added `test_filter_actions_snooze_expired_filter_does_not_shadow_active` in `tests/signal/test_signal_service.py`. It gives a signal two snooze filters on the same entity, one expired a week ago and one valid for 30 more days, and checks the instance ends up snoozed.

The new test fails without the fix and passes with it. I only ran the snooze-related tests in that file (4 passed), not the full suite.