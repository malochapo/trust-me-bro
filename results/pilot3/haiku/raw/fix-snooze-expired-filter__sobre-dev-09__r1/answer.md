Fixed. A snoozed user's new instances are snoozed again, as long as any active snooze filter matches them, even when an expired filter for the same user comes first.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py`), an expired filter hit `break`, which ended the loop over the signal's filters. Any valid snooze filter listed after it was never checked, so the instance wasn't snoozed and a case was opened.

**Fix:** Changed that `break` to `continue` so the loop skips the expired filter and keeps checking the rest.

**Regression test:** Added `test_filter_actions_snooze_after_expired_snooze` in `tests/signal/test_signal_service.py`. It sets up an expired snooze filter followed by an active one for the same entity and asserts the instance is snoozed. It failed before the fix and passes after.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped. I didn't run the full suite.

I haven't committed anything.