Signal filters now have an optional `reason` field, stored in the database and handled by the API and the web UI. The existing signal tests pass (32 passed, 1 skipped), but I added no tests for `reason`. I also didn't run the migration or try the UI.

- **Database:** `SignalFilter` has a new nullable `reason` column. The migration is `2025-09-02_a1c3e5f7b9d2.py` in the tenant revisions. It follows `ff08d822ef2c`, which was the latest revision.
- **API:** `reason` is on the shared filter schema, so create, update and read all accept and return it. I didn't touch the service code, because it copies fields generically.
- **Web UI:**
  - The Snoozes table on the signal instance page has a "Reason" column (not sortable).
  - The create-filter dialog has an optional "Reason" textarea after Description.
  - I added `reason` to the filter store's default state so it resets between dialogs.

I only wired the textarea into the create dialog, as you asked. If the filter edit dialog is a separate component, it doesn't show the field.