Signal filters now have an optional `reason`, stored in the database and exposed through the API and the web UI. The signal test suite passes (32 passed, 1 skipped) against the local PostgreSQL.

**Backend**
- `SignalFilter` gets a nullable `reason` column (`src/dispatch/signal/models.py`).
- `SignalFilterBase` gets `reason: str | None`. Create, update, and read all go through this schema, so the field is accepted and returned with no changes to the views or service.
- Migration `src/dispatch/database/revisions/tenant/versions/2026-10-10_3c7e9a1f5b2d.py` adds the column on top of head `ff08d822ef2c`. I checked the chain by grep: it is the only child of that revision. I did not run it against a database, and I couldn't import Alembic's script directory because the app config needs an env var.

**Frontend**
- The create dialog's final "Save" step has an optional "Reason" textarea next to Description. It is bound to `selected.reason` in the store, which also defaults it to `null`.
- The Snoozes table on the signal instance page has a "Reason" column after Description. It is not sortable.

**Tests**
- I extended `tests/signal/test_signal_filter_service.py`: `test_create` now passes a reason and checks it is stored, and `test_update` checks that updating it works.

**Not verified**
- I did not run the UI, and I couldn't run the formatters: `ruff` isn't installed and the frontend has no `node_modules`. The Vue and JS changes are small and follow the surrounding code, but nothing has exercised them in a browser.