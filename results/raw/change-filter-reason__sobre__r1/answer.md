Signal filters now have an optional `reason` field, stored in the database, accepted by the API on create and update, and shown in the UI. The existing signal tests pass (32 passed, 1 skipped). I added no new tests, did not run the migration, and did not try the UI.

- **Database:** `SignalFilter` has a new nullable `reason` column. The migration is `database/revisions/tenant/versions/2025-09-02_a1c4e7d93b52.py`, following `ff08d822ef2c`. I wrote its date by hand.
- **API:** `reason` is on the shared filter model (`SignalFilterBase` in `signal/models.py`), so create, update and read all handle it. The service code needed no changes.
- **UI:**
  - The Snoozes table on the signal instance page has a "Reason" column, which is not sortable.
  - The create-filter dialog has an optional "Reason" textarea in the final step, next to Description.
  - I added `reason` to the filter store's default state so the textarea starts empty.

I did not add `reason` to the filter's full-text search vector, so it can't be searched on.