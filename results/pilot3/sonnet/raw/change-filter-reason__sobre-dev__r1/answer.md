Signal filters now have an optional `reason` field, stored in the database, accepted by the API and shown and editable in the UI. The signal and filter tests pass (59 passed, 1 skipped). I didn't run the migration or open the UI.

- **Database:** `reason` is a nullable string column on `SignalFilter`. The migration is `2025-09-02_a7c3e51d9b42.py` in the tenant revisions, chained after `ff08d822ef2c`.
- **API:** `reason` is on the base filter schema, so create, update and read all handle it. The existing create and update code passes it through, so I made no service changes.
- **Snoozes table:** `TableInstanceSnoozes.vue` has a new "Reason" column, placed before "Applies to". It isn't sortable.
- **Create dialog:** `SignalFilterCreateDialog.vue` has an optional "Reason" textarea, with `reason` added to the default state in `filter/store.js`.

I didn't add a test for `reason` specifically.