The feature is implemented across the model, migration, API schema, and UI, with tests passing. I didn't commit anything.

**What changed**

- **Database:** `SignalFilter` has a new nullable `reason` String column (`src/dispatch/signal/models.py`). The Alembic migration `src/dispatch/database/revisions/tenant/versions/2026-10-11_3c7e9a1b5d2f.py` adds the column on top of the current head, `ff08d822ef2c`. I checked by parsing the revision files that it is the only head.
- **API:** `reason` is an optional field on `SignalFilterBase`, so it is accepted on create and update and returned on reads. The existing service code already passes the full dict through, so it needed no changes.
- **Web UI:**
  - The Snoozes table on the signal instance page has a "Reason" column (`instance/TableInstanceSnoozes.vue`).
  - The create-filter dialog has an optional Reason textarea in the save step (`filter/SignalFilterCreateDialog.vue`).
  - `reason` is in the store's default state (`filter/store.js`), so it clears between dialogs.
- **Tests:** I added `test_create_with_reason` and `test_update_reason` to `tests/signal/test_signal_filter_service.py`.

**Verification**

- `python -m pytest tests/signal`: 34 passed, 1 skipped.
- I did not run the migration against PostgreSQL, and the Alembic head check failed on a missing `DISPATCH_ENCRYPTION_KEY` env var. The head was verified by parsing the files instead.
- The frontend has no `node_modules`, so I did not build or lint the Vue changes. I did not open the UI in a browser.

**Choices I made**

- `reason` is a plain `String` with no length limit, matching `description`.
- The Reason column is sortable, like Name and Description.
- The Reason field is not required in the dialog.
- The existing edit dialog (`signal/NewEditDialog.vue`) was not changed, since the request only named the create dialog. Editing a filter's reason through the UI will need that dialog updated, or the API alone for now.