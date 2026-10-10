Signal filters now have an optional `reason` field, stored in the database, accepted and returned by the API, and shown and editable in the web UI. The 35 existing signal tests pass (one skipped), but I added no tests for `reason`, didn't run the migration, and didn't load the UI.

- **Database:** `SignalFilter` has a new `reason` string column. The migration is `database/revisions/tenant/versions/2025-09-05_a7c3e91b4d52.py` and follows the current head, `ff08d822ef2c`.
- **API:** `reason` is on the shared filter base schema, so create, update and read all handle it. I didn't change the service code, since it already copies every schema field onto the model.
- **UI:** The Snoozes table on the signal instance page has a "Reason" column, which is not sortable. The "Create Signal Filter" dialog has an optional Reason textarea on the final Save step, below Description. I also added `reason` to the filter store's default state.

I haven't committed anything.