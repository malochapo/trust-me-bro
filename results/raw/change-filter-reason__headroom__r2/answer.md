Signal filters now have an optional `reason` field, stored in the database, accepted and returned by the API, and shown in the UI. The signal tests pass (35 passed, 1 skipped). I didn't run the migration against a database, and I didn't open the UI to check the new column and dialog field.

- **Database:** a new `reason` column (nullable string) on `SignalFilter` in `signal/models.py`. The migration is `2025-09-02_a7c3e91d5b24.py` in the tenant revisions, chained after `ff08d822ef2c`.
- **API:** `reason` is on the shared filter schema in `signal/models.py`, so create, update and read all handle it. The service layer needed no change.
- **UI:** the Snoozes table on the signal instance page has a "Reason" column (not sortable). The create-filter dialog has an optional "Reason" textarea. I also added `reason` to the default state in `signal/filter/store.js`.

I didn't add a test that covers `reason` specifically.