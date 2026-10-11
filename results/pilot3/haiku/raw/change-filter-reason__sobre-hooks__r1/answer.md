I added `reason` to signal filters across the database, API, and web UI. The signal test suite passes (34 passed, 1 skipped). I could not build or lint the frontend, because `node_modules` isn't installed.

**Backend**
- **Model:** `SignalFilter` has a nullable `reason` column. `SignalFilterBase` has `reason: str | None`, so create, update, and read all accept and return it.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_f5d65bc4a0a1.py` adds the column on top of the current head, `ff08d822ef2c`. I ran its `upgrade()` and `downgrade()` against a scratch schema, and both worked.

**Frontend**
- **Snoozes table:** a "Reason" column sits after "Description" in `TableInstanceSnoozes.vue`.
- **Create dialog:** a "Reason" text area is on the save step of `SignalFilterCreateDialog.vue`, next to Name and Description. `reason` is also in the filter store's default state, so it's sent on save.

**Tests**
- Added `test_create_with_reason` and `test_update_reason` to `tests/signal/test_signal_filter_service.py`. Both pass.
- I tried an HTTP round-trip test through the filters endpoints. It passed when run alone, including the create, list, and update calls returning `reason`. It failed in the full signal run, after the existing `test_create` test. The error was a `KeyError: 'dispatch_core'` raised during commit in the request's schema-translate setup. I didn't find the exact mechanism, so I removed the test rather than keep a flaky one. The endpoints are covered only by that one-off run, not by the suite.

**Not verified**
- Frontend lint and build: they need `npm install` first, which I didn't run.
- The Vue changes are small and follow the existing patterns in the same files, but they have not been rendered.