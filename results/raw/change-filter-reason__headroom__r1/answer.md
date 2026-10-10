Signal filters now have an optional `reason` field, stored in the database and handled by the API and web UI. The existing signal tests pass (35 passed, 1 skipped). I didn't run the migration and didn't try the UI.

- **Database:** `SignalFilter` has a nullable `reason` column. The new migration is `2025-09-02_a3b9c1d4e5f6.py` in the tenant revisions, chained after `ff08d822ef2c`, which was the head.
- **API:** `reason` is on the shared filter schema, so create, update and read all accept or return it. The existing create and update services copy fields over, so they needed no changes.
- **UI:**
  - The Snoozes table on the signal instance page has a "Reason" column. It isn't sortable.
  - The create-filter dialog has an optional "Reason" textarea.
  - The filter store's default state includes `reason`.

I didn't add tests for `reason`.