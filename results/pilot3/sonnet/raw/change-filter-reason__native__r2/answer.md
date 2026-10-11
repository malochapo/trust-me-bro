Signal filters now have an optional `reason` field, stored in the database, accepted and returned by the API, and shown in the web UI. I ran `python -m pytest tests -k signal`: 35 passed, 1 skipped. I didn't run the migration or open the UI, and I didn't add a test for `reason` itself.

- **Database:** `SignalFilter` has a new nullable `reason` column in `signal/models.py`. The migration is `2025-09-02_a1c3e5f7b9d2.py` in the tenant revisions, chained after `ff08d822ef2c`, which was the only head. It has a downgrade that drops the column.
- **API:** `reason` is on `SignalFilterBase`, so create, update and read all accept and return it. The existing create and update service code needed no changes.
- **Snoozes table:** a "Reason" column now sits after Description in `TableInstanceSnoozes.vue`. I made it non-sortable.
- **Create dialog:** `SignalFilterCreateDialog.vue` has an optional "Reason" textarea on the Save step, and `signal/filter/store.js` defaults `reason` to null.