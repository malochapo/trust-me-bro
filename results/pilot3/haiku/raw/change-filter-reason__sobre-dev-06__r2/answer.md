Signal filters now have an optional `reason`, stored in the database, accepted on create and update, returned on read, and shown in the UI. The signal test suite passes against the local PostgreSQL (34 passed, 1 skipped). I did not run the frontend, since `node_modules` isn't installed.

**Backend**
- `src/dispatch/signal/models.py`: added a `reason` column to `SignalFilter` and a `reason: str | None` field on `SignalFilterBase`. Create, update, and read all use that base, so the API accepts and returns it with no route changes.
- New migration `src/dispatch/database/revisions/tenant/versions/2026-10-10_b3d2c9a41e87.py` adds a nullable `reason` String column to `signal_filter`. It revises `ff08d822ef2c`, which I confirmed was the only head. I did not run `alembic upgrade` against a live database.

**Frontend**
- `signal/instance/TableInstanceSnoozes.vue`: added a "Reason" column between Description and Applies to. This is the snooze-filter table, not the Triggers table.
- `signal/filter/SignalFilterCreateDialog.vue`: added an optional "Reason" textarea in the Save step, next to Name and Description. It has no validation rule.
- `signal/filter/store.js`: added `reason: null` to the default selected state so the field is sent on save.

**Tests**
- `tests/signal/test_signal_filter_service.py`: added tests for `reason` on create, create with a value, and update.

Ruff reports a pre-existing formatting issue in `models.py` that I did not touch.