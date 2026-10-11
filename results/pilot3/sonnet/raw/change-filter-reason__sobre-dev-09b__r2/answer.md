Signal filters now have an optional `reason`, stored in the database, accepted and returned by the API, and shown and editable in the UI. I ran `tests/signal` and `tests/database` and they pass, but I didn't add a test for `reason`. I also didn't run the migration against a database or start the web UI, so the Reason column and dialog field are unchecked in a browser.

- **Database:** `SignalFilter` has a nullable `reason` column. The migration is `2025-09-02_a1c3e5f7b9d2.py` in the tenant revisions and follows `ff08d822ef2c`. I made up the revision ID and date, so check that they're acceptable.
- **API:** `reason` is on the shared filter schema, so create, update and read all carry it. The existing create and update code copies fields generically, so it needed no changes.
- **UI:**
  - The Snoozes table on the signal instance page has a "Reason" column, which is not sortable.
  - The create-filter dialog has an optional "Reason" textarea on the name and description step.
  - The filter store's default state includes `reason`.