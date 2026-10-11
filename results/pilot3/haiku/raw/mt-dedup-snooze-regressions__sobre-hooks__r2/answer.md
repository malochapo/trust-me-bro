Recap of the three fixes in the working tree, none committed yet:

- **Deduplication windows** (`917a0b7b`): the per-filter window was read as seconds instead of minutes, so a 30-minute filter only grouped instances within 30 seconds. It now reads minutes again, which matches the UI and existing filters. Regression test: `test_filter_actions_deduplicate_window_is_minutes`.
- **Snoozing** (`086dc910`): an expired snooze filter ended the loop with `break`, so valid snooze filters listed after it were never checked. It now uses `continue`. Regression test: `test_filter_actions_snooze_expired_before_valid`.
- **Canary signals** (`a348bbd2`): this commit is the one that made canary signals skip deduplication. I did not change it.

Changelog entries:

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
SNOOZE_BUG: 086dc910c308c8e5a91f5be8b4624cce11feae85
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES