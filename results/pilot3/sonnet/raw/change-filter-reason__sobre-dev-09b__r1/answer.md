Signal filters now have an optional `reason` field, stored in the database, accepted and returned by the API, and shown in the web UI. I ran the existing signal tests (35 passed, 1 skipped). I didn't add a test for `reason` itself, and I haven't run the migration or the UI.

- **Database:** I added a nullable `reason` column to `SignalFilter` in `signal/models.py`. The new migration is `database/revisions/tenant/versions/2025-09-02_a7c3e91d5b24.py`, which follows `ff08d822ef2c`.
- **API:** `reason` is on the shared `SignalFilterBase` schema, so create, update and read all use it. The existing service code needed no changes.
- **Web UI:**
  - The Snoozes table in `TableInstanceSnoozes.vue` has a sortable "Reason" column after Description.
  - The last step of `SignalFilterCreateDialog.vue` has an optional "Reason" textarea.
  - I added `reason: null` to the default state in `signal/filter/store.js`.

I dated the migration 2025-09-02 and gave it a hand-written revision ID, since the previous one was 2025-08-28. Rename it if you want the date to match when you merge.