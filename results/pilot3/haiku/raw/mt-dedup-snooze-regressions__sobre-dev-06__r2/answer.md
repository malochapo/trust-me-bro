**Recap of the fixes (uncommitted in the working tree)**

- **Dedup window in minutes (30-minute filter case).** Commit `917a0b7b` changed per-filter dedup windows from minutes to seconds, so a 30-minute window became 30 seconds. `filter_dedup` now converts the window from minutes again, and the column default in `models.py` is now 60 (minutes). Existing filters work unchanged. A regression test covers it.
- **Expired snooze blocking later snoozes (Okta case).** Commit `086dc910` changed the expired-snooze branch from `continue` to `break`, so one expired filter stopped evaluation of later valid ones. The branch is back to `continue`, with a regression test.
- **Stale docstring.** The `filter_signal` docstring still says the default window is 1 hour. It is 45 minutes. I did not change it.

Tests: `python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite. Nothing is committed.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES