Signal filters now have an optional `reason`, stored in the database, accepted and returned by the API, and shown and editable in the UI. The signal test suite passes (32 passed, 1 skipped).

**Backend**
- `src/dispatch/signal/models.py`: added a nullable `reason` column to `SignalFilter`, and a `reason: str | None` field on `SignalFilterBase`. Create and update inherit it, and reads return it.
- New migration `src/dispatch/database/revisions/tenant/versions/2026-10-11_344dfbf19b95.py` adds the nullable column to `signal_filter`. It revises `ff08d822ef2c`, which I confirmed is the current tenant head.
- The existing create and update service functions already copy schema fields onto the model, so they needed no changes.

**Frontend**
- `instance/TableInstanceSnoozes.vue`: a "Reason" column between Description and "Applies to". It isn't sortable.
- `filter/SignalFilterCreateDialog.vue`: an optional "Reason" text area on the final Save step, bound to `selected.reason`.
- `filter/store.js`: `reason: null` added to the default selected state.

**Tests**
- `tests/signal/test_signal_filter_service.py`: the create and update tests now set and assert `reason`.

**Not verified**
- The migration was checked only for import and revision chaining. I didn't run `alembic upgrade` against PostgreSQL.
- The frontend has no `node_modules`, so I didn't build it or run its linter. The Vue changes follow the existing patterns in those files, but they haven't been exercised in a browser.
- `ruff check` passes on the changed Python files. `ruff format --check` flags a trailing blank line near the end of `models.py` (around line 418). That line was already there and I didn't touch it.

**Choices I made**
- The Reason field is a multi-line `v-textarea`, matching the existing Description field, and it is not required.
- The Reason column is not sortable, since the request didn't ask for sorting.