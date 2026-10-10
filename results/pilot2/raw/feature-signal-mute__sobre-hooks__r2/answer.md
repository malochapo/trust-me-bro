Signal definitions now have an optional `muted_until`, and a muted signal's new instances get filter action `mute` and never open a case. The signal tests pass (34 passed, 1 skipped), including two new ones for an active mute and an expired mute. I didn't run the migration against a database or load the web UI, so the Alembic migration and the Vue changes are untested.

**Backend**
- **Model and API:** `muted_until` is stored on `Signal` and added to `SignalBase`, so it is accepted on create and update and returned on reads. Timezone-aware input is converted to naive UTC, since the column stores UTC.
- **Migration:** `2025-09-02_a7c3d9e15b42.py` adds the column, following `ff08d822ef2c`.
- **Filter action:** `SignalFilterAction.mute` is new.
- **Filtering:** in `filter_signal`, a new `filter_mute` runs first. While `muted_until` is in the future it sets `mute`, and the snooze and dedup filters are skipped. The mute ends by itself once the time passes, because the check compares against the current time.

**Web UI**
- The signal table has a "Muted until" column, which shows the raw timestamp string.
- The create/edit dialog has a datetime-local field labelled "Muted until (UTC)". It sends an explicit UTC timestamp and can be cleared.
- I used a plain datetime field instead of the existing `DateTimePicker` component, which has no confirm button.