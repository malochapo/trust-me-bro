Fixed. In `filter_snooze` (`src/dispatch/signal/service.py`), hitting an expired snooze filter did a `break`, which stopped the loop. Any active filter after it was never checked. I changed that to `continue`, so expired filters are skipped and the rest are still evaluated.

I added a regression test, `test_filter_snooze_skips_expired_filter_and_applies_later_active_filter`, in `tests/signal/test_signal_stats_service.py`. It gives a signal one filter that expired a week ago and one valid for 30 days, both matching the same entity, and checks that the instance gets snoozed. It passes with the fix. With the fix stashed it fails, and the other six tests in that file pass either way.

I only ran that one test file, not the full suite.