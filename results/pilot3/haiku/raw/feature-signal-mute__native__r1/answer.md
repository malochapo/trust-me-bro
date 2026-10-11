Operators can now mute a signal definition until a set time. While muted, new instances are recorded with filter action `mute`, skip snooze and dedup, and don't open a case. The signal test suite passes (34 passed, 1 skipped), including two new mute tests.

**What changed**
- **Model and migration:** `Signal.muted_until` is a nullable timezone-aware `DateTime`. The migration `2026-10-10_5c3e9a1f7b2d.py` chains onto the current head `ff08d822ef2c`, and the chain resolves to a single head.
- **Filter logic:** `SignalFilterAction.mute` is new. `filter_signal` runs a new `filter_mute` step first. If the mute is active, it sets `mute` and skips snooze and dedup. The existing flow already returns early on any filter action, so no case is created. The mute ends on its own because the check compares against the current time.
- **API:** `muted_until` is on `SignalBase`, so create, update, and read all accept and return it. Update uses `exclude_unset`, so omitting the field leaves the mute alone, and sending `null` clears it.
- **Web UI:** The definitions table has a sortable "Muted until" column. The create/edit dialog has a `datetime-local` field that converts to and from ISO. I didn't reuse `DateTimePicker.vue` because it never emits a value. The instance status chip also shows "Muted".

**Choices I made beyond the request**
- In `get_signal_stats`, muted instances no longer count toward "alerted". Without this, they would have been counted as alerts.
- Filter-action tests use a snooze with an empty expression, so a passing test proves snooze was skipped rather than just unmatched.

**Not verified**
- I did not run the frontend build or lint: `node_modules` isn't installed, and `ruff` isn't on the path. The Vue changes are checked by reading only.
- I added no flow-level test for "no case is opened". That behavior depends on the existing early return, which I read but didn't exercise.

**Shared test database:** Another Claude session (`run-9d48523d145a`) was running the full suite against the same `dispatch-test` database at the same time. That caused a "database is being accessed by other users" error on my first run. I retried once it cleared. `conftest.py` hardcodes the database name, so parallel runs will keep colliding until that is changed.