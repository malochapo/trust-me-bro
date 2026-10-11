Signal filters now have an optional `reason`, stored in the database, accepted on create and update, returned on read, shown as a Reason column in the Snoozes table, and editable in the create-filter dialog. The 34 `tests/signal` tests pass (1 skipped), including two new tests for setting `reason` on create and update. I did not run the frontend, because `node_modules` isn't installed here, so the Vue changes are untested beyond reading them.

What changed:

- **Model and API** (`src/dispatch/signal/models.py`): a nullable `reason` column on `SignalFilter`, and an optional `reason` field on `SignalFilterBase`. Because the create and update services already pass Pydantic fields through, the API accepts and returns it with no service changes.
- **Migration** (`src/dispatch/database/revisions/tenant/versions/2026-10-11_3c9e1f7a2b4d.py`): adds the column, with `down_revision = "ff08d822ef2c"`, the previous head. Downgrade drops it. I checked that it is the only leaf by searching for references to each revision, but I did not run the migration against a database.
- **Web UI**:
  - `TableInstanceSnoozes.vue` has a non-sortable "Reason" column.
  - `SignalFilterCreateDialog.vue` has an optional Reason text area on the final step, after Description. I did not add a validation rule.
  - `signal/filter/store.js` adds `reason` to the default state, so it is sent with the save payload.
- **Tests** (`tests/signal/test_signal_filter_service.py`): `test_create_with_reason` and `test_update_reason`.

Choices I made that you may want to change:

- `reason` is a plain `String` with no length limit, matching `description`.
- The Reason field is a multi-line text area, matching Description, rather than a single-line field.