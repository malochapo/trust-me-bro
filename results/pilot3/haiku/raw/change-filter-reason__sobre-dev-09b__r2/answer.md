Signal filters now have an optional `reason`. It is stored, accepted on create and update, returned on read, shown as a "Reason" column in the Snoozes table, and editable in the create dialog. The signal test suite passes (34 passed, 1 skipped), but I could not build or lint the Vue code, and I did not apply the migration to a live database.

**What changed**

- **Model and schema:** `reason` is a nullable `String` on `SignalFilter` (`src/dispatch/signal/models.py`). It is also an optional field on `SignalFilterBase`, which create, update, and read schemas all inherit, so the API picks it up without endpoint changes.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_d441e1501719.py` adds the column to `signal_filter`. It chains onto the previous head, `ff08d822ef2c`. I checked that the tenant revision graph has exactly one head, `d441e1501719`.
- **Snoozes table:** `TableInstanceSnoozes.vue` has a "Reason" column between Description and Applies to. It is not sortable, since the request didn't ask for that.
- **Create dialog:** `SignalFilterCreateDialog.vue` has an optional "Reason" textarea on the Save step, next to Description. `filter/store.js` adds `reason` to the default selected state so it resets between uses.
- **Tests:** `tests/signal/test_signal_filter_service.py` gets two tests. One covers creating a filter with a reason, including reading it back through `SignalFilterRead`. The other covers updating the reason.

**Not verified**

- **Migration:** the test database is built with `create_all`, so the suite never runs the migration. I only checked the revision chain, not the `add_column` / `drop_column` steps against Postgres.
- **Frontend:** there is no `node_modules` in the repo, so I did not build the app or run a lint or type check on the Vue and JS edits.
- **HTTP layer:** the tests call the service functions, not the `/signal/filters` endpoints. The endpoints delegate to the same service code, so I expect them to work, but I didn't exercise them.
- **Formatting:** `ruff` is not installed in this environment, so the Python files were not linted or format-checked.

I did not commit anything.