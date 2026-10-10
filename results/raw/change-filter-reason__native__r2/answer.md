Signal filters now have an optional `reason`, from the database through the API to the web UI. The 35 signal tests pass (1 skipped), but I didn't add a test for `reason` itself. I didn't run the migration against a database or load the UI.

- **Model and API:** `reason` is a nullable column on `SignalFilter` in `signal/models.py`. I added it to `SignalFilterBase`, so create, update and read all accept and return it.
- **Migration:** `database/revisions/tenant/versions/2025-09-02_a1c3e5b7d9f2.py` adds `signal_filter.reason`. It follows the latest tenant revision, `ff08d822ef2c`.
- **Snoozes table:** a sortable "Reason" column in `TableInstanceSnoozes.vue`, placed between Description and "Applies to".
- **Create dialog:** an optional "Reason" textarea in `SignalFilterCreateDialog.vue`, with `reason` added to the filter store's default state in `store.js`.

I didn't add `reason` to the filter's full-text search vector, so it isn't searchable.