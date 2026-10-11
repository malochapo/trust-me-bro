Signal definitions can now be muted until a given time. Muted instances are recorded with filter action `mute`, never open a case, and skip snooze and dedup. The signal tests pass (34 passed, 1 skipped; 37 passed across the suite filtered to signal tests). I haven't committed anything.

**What changed**
- **Model and migration:** `Signal.muted_until` is a nullable DateTime. The new migration is `2026-10-11_cf0daa05e9ea.py`, chained onto the current tenant head `ff08d822ef2c`. It's the only head.
- **Filtering** (`src/dispatch/signal/service.py`): `filter_signal` checks `is_muted()` first. A muted signal sets the instance's `filter_action` to `mute` and skips snooze and dedup. Once `muted_until` passes, the check returns False and normal filtering resumes, so the mute ends on its own.
- **Enum:** `mute` was added to `SignalFilterAction`, which is also the type of `SignalFilter.action`.
- **API:** `muted_until` is on `SignalBase`, so it's accepted on create and update and returned on reads. Create and update pass the schema through `dict()`, so no view changes were needed.
- **UI:** a sortable "Muted until" column in the definitions table, a "Muted until" field in the create/edit dialog (clearing it unmutes), and a "Muted" chip in the instance triggers table.
- **Tests:** `test_filter_actions_mute` checks that a matching snooze is not evaluated while muted and that no case changes. `test_filter_actions_mute_expired` checks that a past mute is ignored.

**Choices I made that you may want to change**
- The "alerted" stat in `get_signal_stats` now excludes `mute`, so muted instances aren't counted as alerted.
- Because `mute` is in the shared enum, `SignalFilter` will accept `action: "mute"`. It has no effect there. Restricting it to instances would need a separate enum.

**Not verified**
- **Timezone:** `muted_until` follows the same convention as filter `expiration`. The stored naive value is treated as UTC, but the dialog's `datetime-local` input is local wall-clock time. For users outside UTC the mute will end at the wrong time. Please check this before relying on it.
- **UI build:** there's no `node_modules` in the UI directory, so the Vue changes haven't been built or linted. I checked them by reading the diff.
- **Migration:** I checked the revision chain and that the file compiles, but didn't run `upgrade` against PostgreSQL.
- **API:** the API path is covered by reading the code, not by a test. No test posts or reads `muted_until` over HTTP.
- **Formatting:** `ruff format` flags `src/dispatch/signal/models.py`, but that was already true before my change, so I left it.