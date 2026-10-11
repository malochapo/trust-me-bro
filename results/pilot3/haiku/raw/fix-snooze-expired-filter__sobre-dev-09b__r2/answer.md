Fixed. A snooze filter that had expired stopped the search through the user's snooze filters, so the later valid one was never checked.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`, around line 763), the expiration check used `break`. When an expired filter came first in the list, the loop ended and the valid filter after it was never evaluated, so the instance was not snoozed.

**Fix:** Changed that `break` to `continue`, so an expired filter is skipped and evaluation moves on to the next one.

**Regression test:** `test_filter_actions_snooze_expired_filter_before_active` in `tests/signal/test_signal_service.py`. It lists an expired snooze for the entity first and an active one second, then asserts the instance is snoozed. It fails on the old `break` code and passes with the fix.

**Results:** The snooze tests pass (4 passed), and the full `tests/signal` suite passes (33 passed, 1 skipped). I didn't run the whole repository test suite.

I couldn't run ruff or black because neither is installed here, so I formatted the new test by hand to match the surrounding style.