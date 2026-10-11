Signal definitions now have an optional `muted_until`, and while it's in the future every new instance is recorded with filter action `mute` and never opens a case. The signal tests pass (33 passed, 1 skipped), including a new one for the mute logic. I haven't run the Alembic migration or loaded the UI, so the frontend changes and the migration are untested.

- **Mute logic:** `filter_signal` in `src/dispatch/signal/service.py` checks `muted_until` first. If it's still in the future, the instance gets `mute` and snooze and dedup filters are skipped. Once the time passes, filtering goes back to normal on its own. `mute` is added to `SignalFilterAction` in `src/dispatch/signal/models.py`.
- **Database:** a nullable `muted_until` DateTime column on `signal`, added by migration `2025-09-02_3c1d5e7a9b2f.py`, which follows the current tenant head `ff08d822ef2c`.
- **API:** `muted_until` is on the shared base schema, so create, update and read all accept and return it. Sending `null` on update clears the mute. Timestamps with a timezone are converted to naive UTC before storing, like the other DateTime columns.
- **Web UI:** the signal definitions table has a "Muted until" column, shown in local time. The create/edit dialog has a clearable `datetime-local` field.
- **Test:** `test_filter_signal_muted` in `tests/signal/test_signal_service.py` covers a muted instance, an expired mute, and the timezone conversion.

I made up the migration's revision ID and its create date (2025-09-02), so rename the file if you want a real timestamp.