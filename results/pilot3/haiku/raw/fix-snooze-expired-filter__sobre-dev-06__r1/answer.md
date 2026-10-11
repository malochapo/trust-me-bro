Fixed. A user with an expired snooze filter and a still-valid one was not being snoozed, because the loop in `filter_snooze` stopped at the first expired filter.

**Root cause:** In `src/dispatch/signal/service.py` (`filter_snooze`), an expired snooze filter hit `break` and ended the loop. Any valid snooze filter evaluated after it was never checked. Changing it to `continue` moves on to the next filter.

**Change:**
- `src/dispatch/signal/service.py:763`: `break` → `continue` for expired snooze filters.
- `tests/signal/test_signal_service.py`: new regression test `test_filter_actions_snooze_expired_filter_before_active_filter`. It puts an expired snooze (7 days ago) before a valid one (30 days out) for the same entity, and asserts the instance is snoozed.

**Verification:**
- The new test fails with the old `break` and passes with the fix.
- `python -m pytest tests/signal` passes (33 passed, 1 skipped).

I did not run the full test suite, only the signal tests.