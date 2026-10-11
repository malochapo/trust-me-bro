Two regressions from the August 2025 refactors are fixed in the working tree. Nothing is committed yet.

- **Dedup windows (`917a0b7b`).** The refactor changed the per-filter lookback from minutes to seconds, but the UI stores minutes. A window of 30 acted as 30 seconds, so related instances opened separate cases. The service now multiplies `f.window` by 60. Existing filters work without being edited. A regression test covers it.
- **Snoozing (`086dc910`).** An expired snooze filter now ended the loop (`break` instead of `continue`), so a valid snooze filter listed after it was never checked. It now skips the expired filter and keeps going. A regression test covers it.
- **Canary signals (`a348bbd2`).** This change was not a bug. Canary instances are no longer deduplicated, and they are excluded when looking for an existing case to group with.
- **Default window.** Signals with no filters use `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. `7a9fe810` made it configurable; before that it was a hard-coded 1 hour.
- **Left alone.** The `SignalFilter.window` column comment and default (3600) in `models.py` still describe seconds. The Pydantic default (600) is inconsistent in the same way. Fixing the DB default would need a migration.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES