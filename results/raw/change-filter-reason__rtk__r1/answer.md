Signal filters now have an optional `reason`, stored in the database, accepted and returned by the API, and shown and editable in the UI. The existing signal tests pass (32 passed, 1 skipped). I didn't add a test for `reason` itself. I also didn't run the Alembic migration or load the web UI.

- **Database:** `SignalFilter` has a new nullable `reason` column. The migration is `2025-09-02_a1c4e7b92d35.py` in the tenant revisions. It comes after `ff08d822ef2c`, which I took to be the latest revision, but I didn't run `alembic heads` to confirm.
- **API:** `reason` is on the shared filter schema, so create, update and read all handle it. No service changes were needed.
- **Snoozes table:** `TableInstanceSnoozes.vue` has a new "Reason" column, placed before "Applies to". I made it non-sortable.
- **Create dialog:** `SignalFilterCreateDialog.vue` has a new optional "Reason" textarea. `filter/store.js` includes `reason` in the default state, so it resets with the rest of the form.

I haven't committed anything.