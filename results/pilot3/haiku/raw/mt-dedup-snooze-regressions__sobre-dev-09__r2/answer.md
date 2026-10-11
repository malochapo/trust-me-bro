## Recap

Three commits since 2025-05-22 caused or changed the reported behavior:

- **`917a0b7b`** changed the filter dedup window from minutes to seconds. A 30-minute window became 30 seconds, so instances ten minutes apart opened separate cases. The fix treats the window as minutes again, which is what the UI sends and what existing filters store. The model comment now says minutes.
- **`086dc910`** changed the expired-snooze branch from `continue` to `break`. An expired snooze filter ahead of a valid one stopped the loop, so new instances were not snoozed. The fix restores `continue`.
- **`a348bbd2`** made filter dedup skip canary signals, and excluded canary instances from dedup lookups.

Regression tests were added for the window units and the expired-before-active snooze case. I did not run the full suite. The signal tests pass (35 passed, 1 skipped, where the skip predates this work). These changes are uncommitted in the working tree.

Open items, not changed:
- The `SignalFilter.window` column default (3600) and the API default (600) are read as minutes, which makes them 60 hours and 10 hours. The intended values are probably 60 and 600 minutes.
- Whether a `null` window from the UI could reach the dedup query is unverified.

```
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```