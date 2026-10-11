Signal filters now have an optional `reason`, stored in the database and accepted on create and update through the API. It is returned on reads, shown as a "Reason" column in the Snoozes table, and editable in the create-filter dialog. The signal test folder passes (34 passed, 1 skipped), and the full suite has 6 failures that were already failing before my changes.

**What changed**
- **Model and schema:** `reason` is a nullable `String` column on `SignalFilter` (`src/dispatch/signal/models.py`). It's also an optional field on `SignalFilterBase`, so create, update, and read all pick it up through the existing `.dict()` paths and the `/filters` endpoints.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_a3c9e1f07b52.py` adds the column and chains from the previous head, `ff08d822ef2c`. A scan of the revision files shows `a3c9e1f07b52` as the single head.
- **Snoozes table:** added a sortable "Reason" column in `TableInstanceSnoozes.vue`.
- **Filter dialog:** added an optional "Reason" textarea in `SignalFilterCreateDialog.vue`, with `reason` in the store defaults in `filter/store.js`.
- **Tests:** added `test_create_with_reason` and `test_update_reason` to `tests/signal/test_signal_filter_service.py`.

**Verification and gaps**
- `python -m pytest tests/signal` passes. Full `python -m pytest` gives 363 passed, 4 skipped, 6 failed. All 6 failures are in `tests/ai/test_ai_service.py`, and they fail the same way with my changes stashed.
- I did not run the Alembic migration against PostgreSQL. Loading the migrations needs the app's `DISPATCH_ENCRYPTION_KEY` config, which isn't set in this environment. I checked the chain statically instead.
- I did not build or lint the Vue frontend, because there's no `node_modules` here. I also couldn't run ruff, which isn't installed. The Vue changes are small and follow the existing patterns in those files, but they have not been rendered.