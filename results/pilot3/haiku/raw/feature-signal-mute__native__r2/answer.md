Muting is implemented across the model, filter logic, migration, and UI. The 16 signal service tests pass, including two new mute tests. Nothing is committed.

**What changed**
- **Model and schema** (`src/dispatch/signal/models.py`): `Signal.muted_until` is a nullable `DateTime` column. `SignalBase` carries it, so create, update, and read all accept and return it. `SignalFilterAction` gains `mute`.
- **Filtering** (`src/dispatch/signal/service.py`): `is_signal_muted()` returns true when `muted_until` is in the future. `filter_signal` checks it first. A muted instance gets `filter_action = mute` and skips snooze and dedup. The flow returns before case creation, so no case opens. Once `muted_until` passes, the check fails and normal filtering resumes, so nothing needs a background job.
- **Migration** (`src/dispatch/database/revisions/tenant/versions/2026-10-10_076ef01ebc8c.py`): adds the column on top of head `ff08d822ef2c`.
- **Web UI**: a "Muted until" column in `signal/Table.vue` and a "Muted until" field in `signal/NewEditDialog.vue`. The field reuses the existing `ExpirationInput` component, which offers the same shortcuts as filter expirations. `signal/store.js` gets the default.
- **Tests** (`tests/signal/test_signal_service.py`): one test checks that a muted signal gets `mute` even when a matching snooze filter exists, with no case attached. Another checks that the mute ends and snooze applies again after `muted_until` passes.

**Choices to review**
- `mute` is added to `SignalFilterAction`, which is also the enum for filter definitions. A `SignalFilter` created with action `mute` would be accepted but do nothing, since snooze and dedup only match their own actions. If you'd rather block that, I can split the enum.
- Timestamps follow the existing `expiration` pattern: a naive stored value is treated as UTC. I didn't check how an offset-aware value from the API is stored.

**Not verified**
- The migration compiles but I did not run it against Postgres.
- The frontend has no `node_modules`, so it is not built, linted, or run in a browser.
- Sorting on the new column is server-side with the default Vuetify behavior; I didn't test it.
- The docs under `docs/docs/administration/settings/signal/` don't mention muting yet.

**Pre-existing failures, unrelated to this change**
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on the clean tree too.
- `black --check` flags `signal/models.py` at the end of the file on the clean tree as well. My edits don't add to that.