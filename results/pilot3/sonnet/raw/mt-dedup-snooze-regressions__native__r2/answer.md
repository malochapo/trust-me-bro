**Recap**

Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated. Two of them caused regressions, and I fixed both in the working tree. Nothing is committed yet.

- **Dedup window bug (`917a0b7b`):** the per-filter window had always been minutes, which is what the UI says. This commit changed it to seconds, so a window of 30 acted as 30 seconds. Instances ten minutes apart opened separate cases. `filter_dedup` now converts the stored value with `f.window * 60`, so existing filters work without being edited. The `SignalFilter.window` column comment now says minutes. A regression test covers it.
- **Snooze bug (`086dc910`):** an expired snooze filter now stopped the loop (`break`) instead of moving on (`continue`). A valid snooze filter listed after an expired one was never checked. I restored `continue`, and a regression test covers it.
- **Canary change (`a348bbd2`):** canary instances are no longer deduplicated, and they are excluded as dedup targets in both the default and per-filter paths. This was intended, not a bug.
- **Default window change (`7a9fe810`):** the window for signals without filters went from a hard-coded 1 hour to a configurable setting that defaults to 45 minutes.

Both new regression tests fail without the fixes. The signal tests pass: 34 passed, 1 skipped.

The column default (`60 * 60`) and schema default (`600`) for `SignalFilter.window` were written as seconds. Read as minutes, they mean 60 hours and 10 hours. I left them alone, and they need a separate decision.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES