Signal filters now take an optional `reason`, stored in the database, accepted and returned by the API, and shown in the UI. `tests/signal` passes (32 passed, 1 skipped), but I didn't run the new migration or try the web UI in a browser. I didn't add a test that sends or reads `reason` through the API either.

- **Model and API:** I added a nullable `reason` column to `SignalFilter` in `signal/models.py`. I also added `reason` to `SignalFilterBase`, so create, update and read all carry it. The existing create and update service code passes it through, so I didn't touch it.
- **Migration:** `2025-09-02_a1c3e5f7b9d2.py` in the tenant revisions adds and drops `signal_filter.reason`. It follows `ff08d822ef2c`, the previous head. I made up the revision ID and the 2025-09-02 date in the filename.
- **Snoozes table:** `TableInstanceSnoozes.vue` has a new "Reason" column, not sortable.
- **Create dialog:** `SignalFilterCreateDialog.vue` has an optional "Reason" textarea on the final Save step. I also added `reason` to the default state in `signal/filter/store.js`.

I left the search vector alone, so `reason` isn't searchable.