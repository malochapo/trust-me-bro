Signal filters now have an optional free-text `reason`, covering the database, the API and the web UI. The signal tests pass (35 passed, 1 skipped), but I didn't write a test for `reason` itself. I also didn't run the migration or try the UI in a browser.

- **Database:** `SignalFilter` has a new nullable `reason` column in `signal/models.py`. The migration is `database/revisions/tenant/versions/2025-09-02_a7c3e91b5d24.py`. It follows the latest revision, `ff08d822ef2c`, and adds or drops the column on `signal_filter`.
- **API:** `reason` is an optional field on the filter schema that create, update and read all share. The existing create and update code handles it, so I didn't change the service.
- **UI:**
  - The Snoozes table in `TableInstanceSnoozes.vue` has a "Reason" column between "Description" and "Applies to".
  - The create-filter dialog (`SignalFilterCreateDialog.vue`) has an optional "Reason" textarea.
  - The filter store's default state includes `reason`, so it clears when the dialog resets.

I left `reason` out of the filter's full-text search vector, so it isn't searchable. Adding it would mean changing the search vector and the migration.