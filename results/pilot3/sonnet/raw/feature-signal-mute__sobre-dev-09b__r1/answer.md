Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are recorded with filter action `mute` and never open a case. The signal tests pass, including two new ones for an active and an expired mute. I did not run the Alembic migration or load the web UI, so the migration and the "Muted until" column and dialog field are untested.

- **Backend:**
  - `muted_until` is a nullable `DateTime` on `Signal`, stored as naive UTC like the other timestamps. It is on the shared base schema, so create, update and read all carry it.
  - `SignalFilterAction` has a new `mute` value.
  - `filter_signal` in `signal/service.py` checks the mute first. While `muted_until` is in the future it marks the instance `mute` and returns, so snooze and deduplication filters are never evaluated.
  - Once the time passes, filtering goes back to normal on its own.
- **Migration:** `2025-09-02_3a1c5e7b9d24.py` adds the `signal.muted_until` column and chains after `ff08d822ef2c`.
- **Web UI:**
  - The signal definitions table has a "Muted until" column that shows the time relative to now, with the full date in a tooltip.
  - The create/edit dialog has a clearable datetime-local field.
  - The field is shown and entered in the browser's local time and sent to the API as UTC.
  - I didn't use the existing `DateTimePicker` component because it never emits an update from its datetime-local input.

I added the two tests to `tests/signal/test_signal_service.py`. I only ran `tests/signal`, not the full suite.