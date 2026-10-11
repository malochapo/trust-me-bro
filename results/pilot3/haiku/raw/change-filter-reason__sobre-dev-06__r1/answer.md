Signal filters now carry an optional `reason`. It's stored, accepted on create and update, returned on read, and shown in the UI. The signal tests pass (34 passed, 1 skipped). The full suite has 6 failures, all in `tests/ai`. Those fail the same way on the clean tree: they try to download a tokenizer, which this sandbox can't reach.

**What changed**

- **Model and schema** (`src/dispatch/signal/models.py`): `SignalFilter` gets a nullable `reason` String column. `SignalFilterBase` gets `reason: str | None`. Create, update, and read all inherit from that base, so the API accepts and returns the field without any service or view changes.
- **Migration** (`src/dispatch/database/revisions/tenant/versions/2026-10-10_3c9e1f5a7d2b.py`): adds `reason` to `signal_filter`, with a matching downgrade. It revises `ff08d822ef2c`, which I computed as the single current head. The chain still has one head.
- **Snoozes table** (`TableInstanceSnoozes.vue`): a "Reason" column sits between Description and Applies to. It isn't sortable, since the backend sort isn't wired for it.
- **Create dialog** (`SignalFilterCreateDialog.vue`, `filter/store.js`): an optional auto-grow "Reason" textarea on the Save step, bound to `selected.reason`. The store's default state includes `reason: null`, and the existing save call sends the whole object, so the value goes through.
- **Tests** (`tests/signal/test_signal_filter_service.py`): added create-with-reason and update-reason cases.

**Not verified**

- The migration hasn't been run against PostgreSQL. The test fixtures build the schema from the models, so the new file isn't exercised. Running `alembic upgrade` on a scratch tenant database would close that gap.
- I didn't run the frontend build or lint, and I didn't click through the UI. The Vue changes follow the existing patterns in those files.

Nothing is committed.