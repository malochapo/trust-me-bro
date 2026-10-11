Here's the recap for the changelog.

**Recap**

- **Deduplication windows:** commit `917a0b7b` changed per-filter `window` from minutes to seconds, while the UI labels it "Window (minutes)". A window of 30 was applied as 30 seconds, so instances ten minutes apart opened separate cases. The fix reads the value as minutes again, so existing filters work without edits.
- **Snoozing:** commit `086dc910` changed an expired snooze filter from `continue` to `break`. An expired filter stopped the check, so later valid snooze filters were ignored. The fix restores `continue`.
- **Canary signals:** commit `a348bbd2` stopped canary signals from being deduplicated, and from serving as dedup matches for other instances.
- **Default grouping:** signals with no filters are grouped over a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`, which replaced the old hard-coded 1 hour).

Both fixes have regression tests, and the signal tests pass against PostgreSQL. Neither fix is committed yet.

```
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```