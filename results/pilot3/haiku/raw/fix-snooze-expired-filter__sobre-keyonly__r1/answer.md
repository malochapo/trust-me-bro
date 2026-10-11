The bug is fixed and a regression test covers it.

**Cause:** In `filter_snooze` (`src/dispatch/signal/service.py:763`), an expired snooze filter hit `break`, which exits the whole loop. Any valid snooze filter later in the list was never checked. So with an expired filter listed first, the user's active filter was skipped and new instances kept opening cases.

**Fix:** Changed that `break` to `continue`, so an expired filter is skipped and evaluation moves on to the next filter.

**Regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It creates an expired filter (7 days ago) followed by an active one (30 days out), both matching the same entity, and asserts the instance is snoozed. I confirmed it fails with the old `break` and passes with the fix.

**Test results:** All 33 tests in `tests/signal` pass, with 1 skipped. Nothing was committed.

One mistake along the way: a shell command I ran included an interactive `git checkout -p`, which stalled and reverted my fix in `service.py`. I re-applied the fix and re-ran the tests, and the diff is now the single-line change plus the test.