I fixed the bug: an expired snooze filter no longer stops later valid filters from being checked. The new regression test fails without the fix and passes with it, and the rest of `tests/signal/test_signal_service.py` still passes (15 passed, 1 skipped).

In `filter_snooze` (`src/dispatch/signal/service.py`), an expired filter hit `break`, which ended the loop. Any valid filter listed after it was never evaluated, so the instance wasn't snoozed. I changed `break` to `continue`.

The test is `test_filter_snooze_skips_expired_filter_and_applies_later_valid_one` in `tests/signal/test_signal_service.py`. It attaches two snooze filters to one signal, one expired a week ago and one valid for 30 days, and checks that the instance ends up snoozed. Both filters have an empty expression, so they snooze every instance. The test therefore doesn't exercise the per-user expression matching from your report.

I haven't committed anything.