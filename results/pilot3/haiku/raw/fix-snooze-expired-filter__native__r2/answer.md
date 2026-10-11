The bug is fixed and the regression test is in place. All 33 signal tests pass (1 skipped).

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`), the loop over a signal's filters used `break` when it hit an expired snooze filter. That exited the loop entirely, so any later snooze filter on the same signal was never checked. In this case the expired filter for the user came first, so the still-valid one was never evaluated and the instances opened cases.

**Fix:** Changed that `break` to `continue` so an expired filter is skipped and evaluation moves on to the next filter. Nothing else changed in the logic.

**Regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It sets up an expired snooze filter followed by an active one for the same entity and asserts the instance is snoozed. I ran it before the fix and it failed (`assert False`), then ran it after the fix and it passed.

I ran the signal test directory with `python -m pytest`, not the full suite.