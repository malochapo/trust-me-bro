Signal filters now have an optional `reason`, stored in the database, accepted on create and update, returned on read, shown as a "Reason" column in the Snoozes table, and editable in the create-filter dialog. The changes are uncommitted in the working tree.

**Backend**
- `src/dispatch/signal/models.py`: added a nullable `reason` column to `SignalFilter`, and a `reason` field on `SignalFilterBase`. Create, update and read schemas all inherit from that base, so the API accepts and returns it without changes to the views or service.
- New migration `src/dispatch/database/revisions/tenant/versions/2025-10-11_a3c9e1f07b25.py` adds the column after the previous head, `ff08d822ef2c`. I checked that it is now the single head.
- Tests in `tests/signal/test_signal_filter_service.py`: added a create-with-reason test and an update-reason test.

**Frontend**
- `filter/SignalFilterCreateDialog.vue`: an optional "Reason" textarea on the Save step, bound to `selected.reason`.
- `filter/store.js`: `reason: null` in the default selected state.
- `instance/TableInstanceSnoozes.vue`: a non-sortable "Reason" column between Description and "Applies to".

**Verification**
- `python -m pytest tests/signal tests/plugins/dispatch_slack/case/test_interactive.py`: 43 passed, 1 skipped.
- `ruff check` passes on the changed Python files. `ruff format --check` flags `models.py` for a blank line before `SignalFilterRead.model_rebuild()`, which was already there before my change, so I left it alone.

**Not verified**
- The migration has not been run against the live PostgreSQL database. The test suite builds tables from the models, not from migrations.
- The Vue changes are not built or run in a browser. `node_modules` is not installed in the frontend directory.