Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are recorded with filter action `mute` and never open a case. `tests/signal` passes (34 passed, 1 skipped), including two new tests for the muted and expired cases. I didn't run the Alembic migration or load the UI in a browser.

- **Mute behavior:** `filter_signal` checks `muted_until` first. If it is in the future, the instance gets `mute` and the function returns early, so snooze and dedup filters never run. Once the time passes, filtering goes back to normal on its own. Timezone-aware values are converted to naive UTC before the comparison.
- **Database:** `muted_until` is a nullable `DateTime` column on the signal model. Its Alembic migration is `2025-09-02_a7c3e91d5b24.py`, which revises `ff08d822ef2c`.
- **API:** `muted_until` is on the base signal schema, so create, update and read all carry it. The existing create and update code copies fields generically, so it needed no other change.
- **UI:**
  - The signal table has a sortable "Muted until" column that shows the time in the browser's local time.
  - The create/edit dialog has a "Muted until" date-time picker, using the same component as the task sheet.
  - `muted_until` is added to the signal store defaults.

The existing per-entity snooze stats count anything that isn't `snooze` as "alerted", so muted instances will show up there as alerted. I left that alone.