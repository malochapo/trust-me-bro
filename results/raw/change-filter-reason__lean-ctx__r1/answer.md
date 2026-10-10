Signal filters now have an optional `reason`, stored in the database, accepted and returned by the API, and shown and editable in the UI. The existing signal tests pass (32 passed, 1 skipped). I haven't run the migration against a database, added a new test for `reason`, or tried the UI.

- **Database:** `SignalFilter` gets a nullable `reason` column, added by a new tenant migration, `2025-09-02_3c1a7d5e9b42.py`. It follows the previous head, `ff08d822ef2c`.
- **API:** `reason` is an optional field on the shared filter schema in `signal/models.py`. Create, update and read all pick it up without further changes.
- **Snoozes table:** `TableInstanceSnoozes.vue` has a "Reason" column after Description. It is not sortable.
- **Create dialog:** `SignalFilterCreateDialog.vue` has an optional "Reason" textarea on the final Save step, next to Description. I also added `reason` to the default state in the filter `store.js`.

The Slack snooze flow still creates filters without a reason, since you didn't ask for it there.