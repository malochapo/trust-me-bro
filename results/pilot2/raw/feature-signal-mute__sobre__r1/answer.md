Signal definitions now have an optional `muted_until`. While it is in the future, each new instance is recorded with filter action `mute` and no case is opened. Snooze and dedup are skipped, and the mute lapses on its own at that time. The signal tests pass (34 passed, 1 skipped). I haven't run the migration or opened the UI, so the Alembic migration and the web changes are untested.

- **Backend** (`signal/models.py`, `signal/service.py`):
  - `SignalFilterAction` gains `mute`, and the `signal` table gets a `muted_until` column.
  - The field is on the shared base schema, so create, update and read all accept and return it.
  - Timezone-aware values are converted to naive UTC before storing, matching the existing timestamps.
  - A new `filter_mute` runs first in `filter_signal`. An already-filtered instance returns early, so no case is created.
- **Migration:** `2025-09-02_a7c3e91d5b24.py`, which revises `ff08d822ef2c`, the previous tenant head.
- **UI:**
  - **Table:** a "Muted until" column (`Table.vue`) shows a relative time with the full date in a tooltip, only while the mute is active.
  - **Dialog:** a `datetime-local` field in the signal create/edit dialog (`NewEditDialog.vue`) converts between the browser's local time and UTC.
  - **Store:** `muted_until` is added to the signal store defaults (`store.js`).
- **Tests:** two new tests in `tests/signal/test_signal_service.py`, one for an active mute (action `mute`, no case) and one for an expired mute (filtering falls through to the normal path).

Muting applies to canary instances too, since the mute check runs before any other filter. Clearing the field in the UI sends `null`, which removes the mute.