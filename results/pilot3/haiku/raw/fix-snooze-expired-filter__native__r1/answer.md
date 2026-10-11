The snooze bug is fixed and a regression test covers it.

**Cause:** `filter_snooze` in `src/dispatch/signal/service.py` walks the signal's snooze filters in order. When it hit an expired filter, it did `break`, which ended the whole loop. Any valid filter listed after the expired one was never checked, so the user's active snooze was ignored and new instances opened cases.

**Fix:** changed that `break` to `continue` (`service.py`, the expiration check), so an expired filter is skipped and evaluation moves on to the next one.

**Regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter followed by an active one for the same entity, and asserts the instance is snoozed. It failed before the fix and passes after.

`python -m pytest tests/signal` passes (33 passed, 1 skipped). I did not run the full suite. I haven't committed anything.