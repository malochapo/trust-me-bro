Signal filters now have an optional `reason` field, stored in the database, accepted and returned by the API, and shown and editable in the UI. The 35 signal-related tests pass (1 skipped). I didn't run the migration itself or open the UI.

- **Database:** I added a nullable `reason` column to `SignalFilter` in `signal/models.py`. The new Alembic migration is `database/revisions/tenant/versions/2025-09-02_a1c3e5b7d9f2.py`, chained after the previous head `ff08d822ef2c`. I made up that revision ID and the 2025-09-02 date, so rename them if you'd rather it follow the repo's convention.
- **API:** I added `reason` to `SignalFilterBase`, so create, update and read all handle it. The service code needed no changes.
- **UI:** The Snoozes table on the signal instance page has a new "Reason" column. I made it non-sortable, which is my call, not something you specified. The create-filter dialog has an optional "Reason" textarea, and I added `reason: null` to the filter store's default state.

I didn't add a test for the new field.