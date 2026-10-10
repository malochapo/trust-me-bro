An expired snooze filter no longer stops the active one from being checked, so the user's new instances are snoozed again.

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py`), the loop did `break` when it hit an expired filter. If the expired filter came before the active one, the active one was never evaluated. I changed the `break` to `continue`.

**Test:** I added `test_filter_actions_snooze_expired_and_active` in `tests/signal/test_signal_service.py`. It puts an expired filter ahead of an active one for the same entity and expects the instance to be snoozed. It fails without the fix and passes with it. I ran only the snooze tests (4 passed), not the full suite.