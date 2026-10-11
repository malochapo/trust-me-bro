Fixed. An expired snooze filter now no longer stops the search, so a valid snooze filter later in the list for the same user still applies.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`), the loop over the signal's filters hit `break` on the first expired snooze filter. That exited the loop before the valid filter was checked. The relationship has no `order_by`, so whether the expired filter came first depended on database order, which is why it looked intermittent.

**Fix:** Changed that `break` to `continue` and added a short comment explaining why.

**Regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It puts an expired filter ahead of an active one for the same entity and asserts the instance is snoozed. I confirmed it fails with the old `break` and passes with the fix.

**Tests:** `tests/signal` and `tests/plugins/dispatch_slack/case/test_interactive.py` pass: 42 passed, 1 skipped.

I haven't committed anything. My temporary edits to check the test were reverted; the diff is only the fix and the new test.