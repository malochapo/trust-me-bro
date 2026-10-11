Signal filters now have an optional `reason`, stored in the database, accepted on create and update, returned on reads, and shown and entered in the UI. The signal and Slack interactive tests pass against the local PostgreSQL (43 passed, 1 skipped). I did not build or run the frontend.

**Backend**
- `src/dispatch/signal/models.py`: added a nullable `reason` column to `SignalFilter` and a `reason: str | None` field on `SignalFilterBase`. That base class is shared by the create, update, and read schemas, so the API accepts and returns it with no view changes. The service's create and update already copy fields generically.
- Migration `src/dispatch/database/revisions/tenant/versions/2026-10-10_3c9d1e7a4b52.py` adds a nullable `reason` String column to `signal_filter`, with a matching downgrade. It revises `ff08d822ef2c`, which was the only head, so the chain still has a single head.
- `tests/signal/test_signal_filter_service.py`: two new tests, one for creating a filter with a reason (checked on the read schema too) and one for updating it.

**Frontend** (`src/dispatch/static/dispatch/src/signal/`)
- `instance/TableInstanceSnoozes.vue`: added a "Reason" column after "Description".
- `filter/SignalFilterCreateDialog.vue`: added an optional, clearable "Reason" textarea on the Save step, bound to `selected.reason`.
- `filter/store.js`: added `reason: null` to the default selected state, so the field is sent on create.

**Not done**
- I did not run the frontend build or any frontend tests.
- `ruff` is not installed in this environment, so I did not run lint or format checks on the Python changes.
- I did not run the migration against a live database; I only checked that it parses and sits at the head.
- The reason is not shown or editable in `NewEditDialog.vue`, which is the edit path for existing filters. You asked only for the create dialog, so I left it alone.