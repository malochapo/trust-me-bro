Signal filters now have an optional `reason`, stored in the database and accepted and returned by the API. The web UI has a Reason column and a Reason field. The backend tests pass; the frontend is untested because there's no `node_modules`.

**Backend**
- `src/dispatch/signal/models.py`: added `reason` to the `SignalFilter` column and to `SignalFilterBase`. Create, update, and read all go through that schema, so no service or view changes were needed.
- New migration `src/dispatch/database/revisions/tenant/versions/2026-10-11_470938caeaec.py` adds a nullable `signal_filter.reason` string column. It revises `ff08d822ef2c`, the only head in the tenant chain. I checked that by grep, not by running alembic, because loading the app config needs settings I didn't have here.

**Frontend**
- `signal/filter/store.js`: `reason` is in the dialog's default state, so it gets sent on create and update.
- `signal/filter/SignalFilterCreateDialog.vue`: an optional "Reason" textarea on the Save step, below Description.
- `signal/instance/TableInstanceSnoozes.vue`: a sortable "Reason" column after Description.

**Tests**
- Added three tests to `tests/signal/test_signal_filter_service.py`: create with a reason, update a reason, and a default of `None`. The filter service tests pass (7 of 7), and `tests/signal` passes (35 passed, 1 skipped).

**Not verified**
- The Vue changes aren't linted, built, or viewed in a browser. Running `npm ci` in `src/dispatch/static/dispatch` and then `npm run lint` would cover the lint part.
- The migration hasn't been run against PostgreSQL.

**Choices I made**
- `reason` is a plain nullable `String` with no length limit, and it isn't added to the full-text search vector.
- The Reason column is sortable, matching Name and Description.

Nothing is committed.