The `muted_until` feature is in place across the database, API, filter pipeline, and web UI. The new and existing signal tests pass. The Vue changes are not built or linted, because the repo has no `node_modules`.

**What changed**

- **Model and migration:** `Signal.muted_until` is a nullable `DateTime(timezone=True)`. The migration `2026-10-11_e9fb5bc72a69.py` is the new head of the tenant chain, on top of `ff08d822ef2c`. I chose a timezone-aware column because the date picker already sends UTC ISO strings.
- **API:** `muted_until` lives on `SignalBase`, so it is accepted on create and update and returned on read.
- **Filtering:** `filter_mute` runs first in `filter_signal`. While the mute is active it sets `filter_action = mute`. Snooze and dedup run only if nothing was set, so a muted instance never gets a `case_id` and never opens a case. The mute ends on its own when the timestamp passes, with no background job. Instances are still stored as before.
- **Stats:** muted instances are excluded from `num_signal_instances_alerted`, as snoozed ones already were.
- **UI:**
  - A "Muted until" column in the signal definitions table.
  - A date-time picker in the create/edit dialog, with a short hint.
  - Muted instances show as "Muted" in the instance triggers table; without this they would have shown as "Not Filtered".

**Tests**

- Three new tests in `tests/signal/test_signal_service.py`: an active mute overrides an active snooze filter and creates no case; an expired mute has no effect; the schema parses `muted_until`.
- `tests/signal` passes in full.
- `tests/database` has one failure, `test_restricted_case_filter_with_test_data`. It fails the same way with my changes stashed, so it predates this work.
- Ruff lint passes on the changed Python files.

**Choices to check**

- `mute` is a member of `SignalFilterAction`, so it is also accepted when creating a `SignalFilter` through the API. A filter with that action would be silently ignored. I can reject it at the schema level if you prefer.
- The migration was checked by reading the chain and by the test suite's schema setup. I did not run `alembic upgrade` against a live database.