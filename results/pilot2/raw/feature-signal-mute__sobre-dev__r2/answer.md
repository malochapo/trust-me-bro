Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are recorded with filter action `mute` and never open a case. The signal tests pass (33 passed, 1 skipped), including a new one for muting and for the mute expiring. I haven't run the Alembic migration, and I haven't loaded the web UI, so the column and dialog are untested.

**Backend**
- **Model and API:** `muted_until` is a nullable `DateTime` column on `Signal`. It's accepted on create and update and returned on read through `SignalBase`.
- **Migration:** `2025-09-02_a7c3e91d4b52.py` adds the column; it follows the previous latest revision `ff08d822ef2c`.
- **Filtering:** `filter_signal` checks `muted_until` first. If it's in the future, the instance gets `mute` and the function returns immediately, so snooze and deduplication are skipped. The existing flow already stops for any filtered instance, which is why no case is created. Once the time passes, the signal is processed normally with no cleanup needed.
- **Enum:** I added `mute` to `SignalFilterAction`.
- **Test:** `test_filter_signal_muted` in `tests/signal/test_signal_service.py`.

**Web UI**
- **Table:** `signal/Table.vue` has a "Muted until" column showing a relative date with a full-date tooltip.
- **Dialog:** `signal/NewEditDialog.vue` has a "Muted until" date-time picker, and `store.js` has the new field in its default state.

One thing to know: the date-time picker has no clear button. To remove a mute, an operator has to set a time in the past, or clear it through the API.