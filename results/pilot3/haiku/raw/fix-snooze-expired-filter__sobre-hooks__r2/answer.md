The bug is fixed and a regression test covers it. The new test fails without the fix and passes with it, and the full `tests/signal` suite passes (33 passed, 1 skipped).

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter hit `break`, which ended the loop over the signal's filters. If the expired filter came first, the valid filter for the same user was never checked, so new instances weren't snoozed.

**Fix:** Changed that `break` to `continue`, so an expired filter is skipped and evaluation moves on to the next filter. This matches how filters with no expiration are already handled a few lines above.

**Test:** `test_filter_actions_snooze_expired_filter_before_valid` in `tests/signal/test_signal_service.py` lists an expired filter (7 days ago) ahead of a valid one (30 days out) for the same entity, and asserts the instance is snoozed.

I didn't change the Slack snooze-creation code or the stats query. The bug report describes the snooze check, and that's where the fix is.