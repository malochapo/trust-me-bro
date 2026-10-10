Signal filters now have an optional `reason` field, stored in the database, accepted and returned by the API, and shown in the UI. The existing signal tests pass (32 passed, 1 skipped). I didn't add a test for `reason` itself, run the migration, or try the UI.

- **Model and API:** I added a nullable `reason` column to `SignalFilter` in `signal/models.py`, and added `reason` to the shared pydantic base so create, update and read all include it. The service code copies fields generically, so it needed no change.
- **Migration:** `2025-09-02_a1c3e5b7d9f2.py` adds and drops the column. It follows the latest tenant revision, `ff08d822ef2c`.
- **UI:** The Snoozes table in `TableInstanceSnoozes.vue` has a new "Reason" column, which is not sortable. The create-filter dialog in `SignalFilterCreateDialog.vue` has a new optional "Reason" textarea, and `reason` is added to the default state in `signal/filter/store.js`.

I left `reason` out of the filter's full-text search vector, so searching won't match on it.