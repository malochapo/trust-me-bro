Signal definitions now have an optional `muted_until`, and new instances of a muted signal are filtered with the new `mute` action. The signal tests pass (33 passed, 1 skipped), including a new one for muting. I didn't run the migration or the web UI.

**Backend**
- **Model:** `muted_until` is a nullable `DateTime` on `Signal`, with a matching optional field on the base API schema. Create, update and read all carry it, so the API accepts and returns it.
- **Filter action:** `SignalFilterAction.mute` is added to the enum. At the top of `filter_signal` (`signal/service.py`), if `muted_until` is in the future, the instance gets `mute` and the function returns `True` straight away. Snooze and dedup are never evaluated, and no case is opened.
- **End of mute:** nothing needs to run when the time passes. Once `muted_until` is in the past, the next instance is filtered normally.
- **Migration:** `2025-09-02_a3c1e5d79b24.py` adds and drops the column, chained after the latest revision `ff08d822ef2c`.
- **Time zone:** like the existing filter expirations, `muted_until` is stored as a naive datetime and compared as UTC.

**Web UI**
- **Table:** `signal/Table.vue` has a "Muted until" column, shown as `YYYY-MM-DD HH:mm UTC`.
- **Dialog:** `signal/NewEditDialog.vue` has a "Muted until (UTC)" `datetime-local` field. Clearing it unmutes the signal.

I added `test_filter_signal_muted`, which checks that an active mute filters the instance and that an expired one doesn't.