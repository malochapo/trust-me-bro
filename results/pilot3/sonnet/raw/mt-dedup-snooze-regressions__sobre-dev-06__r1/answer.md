**Recap**

Two regressions came from commits labelled as refactors, and both are fixed in the working tree. I haven't committed anything.

- **Dedup windows:** `917a0b7b` switched the per-filter lookback from minutes to seconds. The UI stores minutes (5–30), so a window of 30 acted as 30 seconds and instances ten minutes apart opened separate cases. The window is read as minutes again, so existing filters work unedited. I also changed the `SignalFilter.window` column default from `3600` to `60` and the API schema default from `600` to `10`, both now in minutes.
- **Snoozing:** `086dc910` changed `continue` to `break` for expired snooze filters. An expired filter listed before a valid one stopped the loop, so the valid snooze never applied. It is back to `continue`.
- **Tests:** I added a regression test for each fix. Both fail without the fixes, and `python -m pytest tests/signal` passes with them (34 passed, 1 skipped).
- **Other commits:** `a348bbd2` made canary signals skip deduplication and excluded them from dedup matches. `7a9fe810` made the default no-filter window configurable, changing it from 1 hour to 45 minutes.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES