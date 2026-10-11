Muting is implemented end to end: a signal definition gets an optional `muted_until`, and while it's in the future, new instances are recorded with filter action `mute`, never open a case, and skip snooze and dedup. The mute expires on its own because the check compares against the current time. The signal tests pass (34, plus 2 new mute tests). The full suite has 8 failures, which also fail on the untouched baseline, so they predate this change.

**What changed**

- **Model and migration:** `Signal.muted_until` is a nullable column, and `mute` is added to `SignalFilterAction`. The migration is `2026-10-10_6b1d3f2a9c4e.py` in the tenant revisions, chained onto the current head `ff08d822ef2c`.
- **API:** `muted_until` is on `SignalBase`, so it's accepted on create and update and returned on read. Setting it to `null` on update unmutes the signal.
- **Filtering** (`src/dispatch/signal/service.py`): a new `filter_mute` step runs first in `filter_signal`. Snooze and dedup only run if nothing has been set yet, so a muted instance is never snoozed or deduplicated.
- **Web UI:**
  - The definitions table has a "Muted until" column.
  - The create/edit dialog has a "Muted until" picker, with an Unmute button to clear it.
  - Muted instances show as "Muted" in the instance status column.
- **Tests:** two new tests in `tests/signal/test_signal_service.py`. One checks that a muted instance gets `mute`, skips an active snooze with no expression and a dedup target, and creates no case. The other checks that an expired mute doesn't filter.

**Choices I made**

- `muted_until` is `DateTime(timezone=True)`, unlike the naive `expiration` column. A tz-aware value sent by an API client would otherwise be stored with its offset silently dropped.
- The dialog has an explicit Unmute button, because the date picker component has no clear action.
- `mute` is in the shared `SignalFilterAction` enum, so the API will also accept a `SignalFilter` with action `mute`. That filter would do nothing, since snooze and dedup ignore it. I didn't block it; say if you want that rejected.

**Not verified**

- The migration hasn't been run against the local PostgreSQL. I checked that it compiles and that its head is correct.
- The frontend hasn't been built or linted. `node_modules` isn't installed in this checkout, so the Vue changes are checked by reading only.