I added `reason` to signal filters across the database, API, and UI. The backend tests pass. I could not run the frontend build or an end-to-end API test, so the Vue changes and the HTTP path are checked by reading the code only.

**What changed**
- **Model** (`src/dispatch/signal/models.py`): a nullable `reason` column on `SignalFilter`, and an optional `reason` on `SignalFilterBase`. Create, update, and read all inherit it, and the service already passes the schema through `.dict()`, so no service change was needed.
- **Migration** (`src/dispatch/database/revisions/tenant/versions/2026-10-10_3c7e9a1f5d2b.py`): adds the column to `signal_filter`, revising the previous head `ff08d822ef2c`. The downgrade drops it.
- **Dialog** (`filter/SignalFilterCreateDialog.vue`): an optional "Reason" textarea in the Save step, next to Name and Description. It is bound to `selected.reason`.
- **Store** (`filter/store.js`): `reason: null` in the default selected state, so it is sent on create and update.
- **Snoozes table** (`instance/TableInstanceSnoozes.vue`): a "Reason" column between Description and "Applies to". It is not sortable.

**Tests**
- Added to `tests/signal/test_signal_filter_service.py`: create with reason, update reason, and a schema test that create, update, and read models accept and return `reason`.
- `tests/signal` runs at 35 passed, 1 skipped; the filter service file is 7 passed.

**Not verified**
- **HTTP endpoints:** I tried an end-to-end test through `/api/v1/default/signals/filters` and gave up. The test fixtures don't wire the middleware's organization DB session, which fails with a `dispatch_core` KeyError. I removed that test rather than leave it broken. The endpoints themselves are unchanged; they pass the same Pydantic models the tests cover.
- **Migration:** I checked that it compiles and chains onto the single head. I did not run it against PostgreSQL.
- **Frontend:** `node_modules` is missing, so I did not run a build or lint. The Vue changes follow the existing patterns in those files.

**Choices I made**
- The reason is free text, nullable, and unrestricted in length, using `String` like `description`.
- The Snoozes column is not sortable, since sorting is server-side and the API has no sort key for it.
- Update uses the same full-replacement semantics as `description`: an update that omits `reason` clears it.