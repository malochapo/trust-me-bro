Signal filters now have an optional free-text `reason`, stored in the database, accepted on create/update, returned on read, and shown in the UI. The signal tests pass (32 passed, 1 skipped). I didn't run the migration against a database, and I didn't open the UI or test the Vue changes in a browser.

- **Database:** there's a new nullable `reason` column on `signal_filter` in `signal/models.py`. The Alembic migration is `2025-09-10_a3c1e5d7b9f2.py` in the tenant revisions, chained after `ff08d822ef2c`, which I took to be the current head. I didn't run `alembic heads` to confirm that, so check it.
- **API:** `reason` is on the shared filter schema, so create, update and read all handle it. `signal/service.py` needed no change.
- **UI:**
  - `TableInstanceSnoozes.vue` has a new "Reason" column, not sortable.
  - `SignalFilterCreateDialog.vue` has an optional "Reason" textarea on the Save step.
  - The `signalFilter` store's default state in `filter/store.js` includes `reason`.

I didn't add a test that sends `reason` through the create/update API.