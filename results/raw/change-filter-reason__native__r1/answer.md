Signal filters now have an optional `reason` field, from the database through the API to the UI. The existing signal tests pass (32 passed, 1 skipped). I didn't add a test for `reason`, run the migration, or try the UI in a browser.

- **Database:** `SignalFilter` has a nullable `reason` string column. The new migration is `database/revisions/tenant/versions/2025-09-02_a7c1e5d93b42.py` and follows the latest existing revision, `ff08d822ef2c`.
- **API:** `reason` is on the shared filter schema in `signal/models.py`, so create, update and read all handle it. The existing create and update code passes it through, so I made no service changes.
- **Snoozes table:** `TableInstanceSnoozes.vue` has a new sortable "Reason" column, placed before "Applies to".
- **Create dialog:** `SignalFilterCreateDialog.vue` has an optional "Reason" textarea after Description. `store.js` defaults `reason` to null.

The migration filename date and revision ID are my own choices. I assumed `ff08d822ef2c` is the only current head and didn't check for other heads.