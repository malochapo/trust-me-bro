Signal filters now have an optional `reason`, stored, accepted and returned by the API, and shown in the UI. The signal tests pass (35 passed, 1 skipped). I didn't run the migration or try the UI in a browser, and I added no new tests for `reason`.

- **Database:** `SignalFilter` has a nullable `reason` column. The Alembic migration is `2025-09-02_a1c3e5b7d9f2.py` in the tenant revisions, chained after `ff08d822ef2c`.
- **API:** `reason` is an optional field on the shared filter schema, so create, update and read all handle it. The existing service code needed no change.
- **UI:** the Snoozes table on the signal instance page has a sortable "Reason" column. The create-filter dialog has an optional "Reason" textarea, and the filter store's default state includes the field.

Sorting by the new column depends on the server accepting `reason` as a sort field. I didn't check that.