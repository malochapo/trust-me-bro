Signal definitions now have an optional `muted_until`, and a muted signal's new instances are recorded with filter action `mute` and never open a case. The backend tests pass, including two new ones. I didn't run the web UI or the migration.

- **Backend:** `muted_until` is a new nullable `DateTime` column on `Signal`, added by a migration at `database/revisions/tenant/versions/2025-09-02_a7c3e91d5b24.py`. It is accepted on create and update and returned on read. I added `mute` to `SignalFilterAction`.
- **Filtering:** in `filter_signal`, a signal with `muted_until` in the future gets `mute` before anything else, so snooze and deduplication filters are skipped. Once the time passes, filtering goes back to normal, so the mute ends by itself.
- **Time zones:** timestamps with a timezone offset are converted to naive UTC on the way in, matching the other timestamp columns.
- **UI:** the signal definitions table has a sortable "Muted until" column. The create/edit dialog has a datetime-local input for it, which can be cleared. The UI works in local time and converts to and from UTC.
- **Tests:** `test_filter_signal_muted` and `test_filter_signal_mute_expired` are in `tests/signal/test_signal_service.py`; the full `tests/signal` run gives 34 passed, 1 skipped.

The Instances table in `TableInstanceTriggers.vue` only labels `snooze` and `deduplicate`, so a muted instance would show there as "Not Filtered". I left it alone since you didn't ask for it, but it's a small addition if you want a "Muted" label.