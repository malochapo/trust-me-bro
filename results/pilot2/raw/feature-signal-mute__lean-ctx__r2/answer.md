Signal definitions now have an optional `muted_until` timestamp, and a signal that is muted at the time an instance arrives has that instance filtered with the new `mute` action. The signal tests pass (34 passed, 1 skipped), including two new ones for active and expired mutes. I haven't run the Alembic migration or loaded the web UI, so both are untested.

- **Filtering:** `filter_signal` in `signal/service.py` checks `muted_until` first. If it's in the future, the instance is stored with `filter_action = mute` and snooze and dedup are skipped. `signal_instance_create_flow` returns early for filtered instances, so no case is opened. Once the time passes, filtering goes back to normal on its own.
- **Model and API:** the column and the pydantic field are in `signal/models.py`, and a new `SignalFilterAction.mute` value is added. The existing create/update code copies the field, so it is accepted on create and update and returned on read.
- **Migration:** `2025-09-02_3b1c7d5e9a42.py` adds a nullable `signal.muted_until` column on top of the current head, `ff08d822ef2c`.
- **UI:**
  - The signal definitions table has a sortable "Muted until" column, shown with `formatDate`.
  - The create/edit dialog has a "Muted until" date-time picker, using the existing `DateTimePickerMenu`.
  - `muted_until` is added to the signal store's default state.

The column is a naive `DateTime`, like `SignalFilter.expiration`. A stored value with no timezone is treated as UTC when compared.

The two new tests are in `tests/signal/test_signal_filter_service.py`.