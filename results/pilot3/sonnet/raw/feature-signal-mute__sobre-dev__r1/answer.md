Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are filtered with the new `mute` action. The signal tests pass (34 passed, 1 skipped), including two new ones. I didn't run the migration against a database or load the web UI.

- **Model and API:** `muted_until` is a nullable column on `Signal`, and `mute` is added to `SignalFilterAction`. The field is on the shared base schema, so it is accepted on create and update and returned on read.
- **Migration:** `database/revisions/tenant/versions/2025-09-02_3c1d9a7e5b42.py` adds the column. It follows the latest existing revision, `ff08d822ef2c`.
- **Filtering:** `filter_signal` in `signal/service.py` checks for a mute first. While `muted_until` is in the future, the instance is marked `mute` and the snooze and deduplication filters are skipped. Once the time passes, filtering goes back to normal on its own, with no cleanup job.
- **Web UI:** `Table.vue` has a "Muted until" column and `NewEditDialog.vue` has a datetime field, both wired through `store.js`.
- **Tests:** two new tests in `tests/signal/test_signal_service.py` cover an active mute and an expired mute.

**Timezone:** the column is a timezone-naive `DateTime`, like the existing snooze `expiration`, so values are treated as UTC. The table shows the time as UTC, and the dialog field is labelled "Muted until (UTC)". The browser's `datetime-local` input has no timezone, so users have to enter UTC.

**Existing cases:** muting doesn't touch cases that are already open.