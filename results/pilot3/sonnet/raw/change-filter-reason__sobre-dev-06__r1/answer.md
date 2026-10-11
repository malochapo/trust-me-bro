Signal filters now have an optional free-text `reason`, stored in the database, accepted and returned by the API, and shown in the UI. The existing signal tests pass (32 passed, 1 skipped), but I didn't add a test for `reason` and haven't run the migration or looked at the UI in a browser.

- **Database:** a new nullable `reason` column on `SignalFilter` in `signal/models.py`. The migration is `2025-09-02_a7c3e91d5b24.py` in the tenant revisions. It chains onto `ff08d822ef2c`, which was the latest revision.
- **API:** I added `reason` to the shared `SignalFilterBase` schema, so it's accepted on create and update and returned on read. The service code needed no changes, because it copies fields from the request onto the filter.
- **Snoozes table:** a "Reason" column after "Description" in `TableInstanceSnoozes.vue`. I set it as not sortable, since I didn't think sorting by it was needed. Say if you want it sortable.
- **Create dialog:** an optional "Reason" textarea on the name and description step of `SignalFilterCreateDialog.vue`, with `reason` added to the filter store's default state.

I didn't touch the edit dialog for filters, so users can set a reason through the API and the create dialog but not the edit UI.