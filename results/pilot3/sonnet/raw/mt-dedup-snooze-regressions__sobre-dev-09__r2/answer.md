Two commits since 2025-05-22 introduced regressions in signal filtering. I fixed both in the working tree and added a regression test for each. Nothing is committed.

- **Deduplication windows:** `917a0b7b` presented itself as a refactor but changed a filter's `window` from minutes to seconds. The UI offers windows of 5 to 30 minutes, so a window of 30 acted as 30 seconds. Instances ten minutes apart opened separate cases. `window` is minutes again, and existing filters work without edits or a migration. I also changed the stored and schema defaults to 60 minutes. Both previously assumed seconds, at 3600 and 600.
- **Snoozing:** `086dc910` presented itself as a refactor but changed an expired snooze filter from `continue` to `break`. An expired filter listed first stopped the loop, so a valid filter after it was never checked. It now skips the expired filter and keeps checking.
- **Canary signals:** `a348bbd2` stopped canary signals from being deduplicated. Canary instances are skipped by dedup and ignored when looking for earlier instances. I did not change this.
- **Default window:** `7a9fe810` made the default dedup window configurable. It replaced a fixed 1 hour with a 45-minute default for signals without filters, so the default quietly dropped by 15 minutes. I did not change this either.

`python -m pytest tests/signal` gives 34 passed and 1 skipped. Each new test fails without its fix.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES