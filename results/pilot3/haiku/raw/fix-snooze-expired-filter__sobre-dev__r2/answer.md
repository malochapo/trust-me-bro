Fixed. A snooze filter that had expired stopped the whole loop, so a later, still-valid snooze filter for the same user was never checked.

**Cause:** in `filter_snooze` (`src/dispatch/signal/service.py:763`), the expired-filter branch used `break`. That exits the loop over the signal's filters, so an active snooze filter listed after an expired one was never evaluated. The fix changes it to `continue`, which skips only the expired filter.

**Regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter (7 days ago) followed by an active one (30 days out), both matching the same entity, and asserts the instance is snoozed. It fails on the old code and passes with the fix.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped. I did not run the whole suite.

The filters relationship has no `order_by`, so the test controls order by listing the expired filter first, as in the report. The behavior is the same in any order, since the bug only triggers when an expired filter comes before the valid one.