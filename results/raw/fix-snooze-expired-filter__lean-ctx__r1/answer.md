Fixed. An expired snooze filter no longer stops the later, still-valid filters from being checked, so new instances for that user are snoozed again.

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py`), hitting an expired filter ran `break`, which ended the loop. Any valid filter listed after the expired one was never evaluated. The fix is to change that `break` to `continue`.

**Test:** I added `test_filter_actions_snooze_expired_then_valid` to `tests/signal/test_signal_service.py`. It gives a signal one snooze filter that expired 7 days ago and one valid for 30 days, both matching the same entity. It then checks the instance ends up snoozed.

**Results:**
- The new test fails without the fix.
- All 4 snooze tests pass with the fix.
- I only ran the snooze tests, not the full suite.