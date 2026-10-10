Fixed. In `filter_snooze` (`src/dispatch/signal/service.py`), hitting an expired snooze filter did a `break`, which ended the loop before any later filters were checked. It is now `continue`, so expired filters are skipped and the remaining ones are still evaluated.

I added `test_filter_actions_snooze_expired_and_valid` in `tests/signal/test_signal_service.py`. It gives a signal one snooze filter that expired 7 days ago and one valid for 30 more days, both matching the same entity. It then checks that the instance gets snoozed.

The new test fails with the fix stashed and passes with it. All of `tests/signal/test_signal_service.py` passes (15 passed, 1 skipped). I did not run the rest of the suite.