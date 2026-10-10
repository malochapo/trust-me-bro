I fixed the bug. A user with one expired snooze filter and one valid one is snoozed again, so new instances stop opening cases.

**Cause:** `filter_snooze` in `src/dispatch/signal/service.py` looped over the signal's filters and used `break` when it reached an expired one. That ended the whole loop, so a valid snooze filter later in the list was never checked. With only one filter it worked, and it broke once an expired filter came before a valid one.

**Fix:** I changed that `break` to `continue`, so an expired filter is skipped and the loop moves on to the next one.

**Test:** I added `test_filter_snooze_skips_expired_filter` to `tests/signal/test_signal_service.py`. It gives a signal one expired and one valid active snooze filter and checks that the instance ends up snoozed. It fails without the fix and passes with it, and the rest of that file still passes.

The test uses filters with no expression, so it covers the "snooze regardless of entity" path. The user-specific case in the report goes through the expression-matching path. The `break` was the same for both, so the fix applies to both, but I didn't write a separate test for that path.

I haven't committed anything.