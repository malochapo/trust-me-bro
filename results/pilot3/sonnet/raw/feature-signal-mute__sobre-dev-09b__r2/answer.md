Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are filtered with the new `mute` action and never open a case. The signal tests pass (34 passed, 1 skipped). I didn't run the Alembic migration or load the web UI, so the migration and the UI changes are untested.

**Backend**
- **Model and API:** `muted_until` is a nullable `DateTime` column on `Signal` and a field on the base schema. It is accepted on create and update, and returned on read.
- **Migration:** `2025-09-02_3c1a7e5d9b42.py` in the tenant revisions adds the column, on top of the current head `ff08d822ef2c`.
- **Filtering:** `filter_signal` now checks the mute first. While `muted_until` is in the future, the instance gets `SignalFilterAction.mute` and the snooze and deduplication filters are skipped. Once the time passes, filtering goes back to normal on its own.
- **Tests:** I added two to `tests/signal/test_signal_service.py`, one for a currently muted signal and one for an expired mute.

**Web UI**
- **Table:** `signal/Table.vue` has a "Muted until" column.
- **Dialog:** `signal/NewEditDialog.vue` has a "Muted until" field that reuses the `ExpirationInput` date and time picker.
- **Store:** `muted_until` is added to the signal store's `selected` object.

The picker sends a local time without a timezone, and the backend treats stored times as UTC. Snooze filter expirations already behave this way, so I kept it consistent. For operators outside UTC, that means a mute could end earlier or later than the local time they picked.