Signal definitions now have an optional `muted_until`, and a muted signal's new instances are recorded with filter action `mute` and never open a case. The signal tests pass (34 passed, 1 skipped), including two new ones for muted and expired mutes. I haven't run the Alembic migration or opened the web UI, so those parts are untested.

- **Model and API:** `muted_until` is on the `Signal` model and on the shared base schema, so create, update and read all carry it.
- **Filter behavior:** `mute` is a new `SignalFilterAction`. `filter_signal` checks the mute first, so snooze and deduplication filters aren't evaluated while it's active, and it returns "filtered". Once the time passes, filtering goes back to normal.
- **Migration:** `2025-09-02_a7c3e91d5b24.py` adds a nullable `muted_until` column to `signal`. It sits after `ff08d822ef2c`, which was the only head. I made up the revision ID and date, so rename them if you prefer.
- **UI:** the signal table has a sortable "Muted until" column, and the create/edit dialog has a "Muted until" date-time picker with a one-line note about what muting does.

The column is a naive `DateTime`, and the code treats stored values as UTC, the same way snooze filter expirations are handled.