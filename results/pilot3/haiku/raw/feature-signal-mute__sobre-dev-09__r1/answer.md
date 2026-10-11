Muting is implemented across the model, migration, filter logic, API, and web UI. The signal, project, and case test suites pass, but I haven't built or linted the Vue code and haven't run the migration against Postgres.

**What changed**

- **Model and migration:** `Signal.muted_until` is a nullable timezone-aware `DateTime`. The migration is `2026-10-11_4ffaba23a655.py`, chained onto the current head `ff08d822ef2c`. I checked that it is the only head.
- **Filter logic:** `filter_signal` first calls a new `filter_mute`. If the definition is muted (`muted_until` is in the future), the instance gets `filter_action = mute` and snooze and dedup are skipped. The existing early return in `signal_instance_create_flow` then stops case creation. Once `muted_until` passes, the check simply stops matching.
- **API:** `muted_until` is on `SignalBase`, so it is accepted on create and update and returned on read with no other changes.
- **Web UI:** a "Muted until" sortable column in the signal definitions table, a `datetime-local` field in the create/edit dialog, and a "Muted" chip in the instance triggers table.
- **Tests:** three service tests (active mute, mute overriding a snooze and a dedup, expired mute) and one flow test that a muted instance is recorded but creates no case.

**Choices you may want to change**

- **`mute` is added to the shared `SignalFilterAction` enum.** The spec called it a filter action, and instance `filter_action` is a plain string column, so no enum migration was needed. The side effect is that the API will also accept `action: "mute"` on a `SignalFilter`, where it is inert. The web filter dialog only offers snooze and deduplicate, so this only happens via direct API calls. Validating against it would be a small follow-up.
- **`muted_until` is timezone-aware,** unlike the existing naive `expiration` column. This avoids Postgres silently dropping the offset from timestamps sent with a non-UTC offset.
- **The dialog converts times in both directions.** The browser's local `datetime-local` value is sent as a UTC ISO string, and the stored value is shown back in local time.

**Verification**

- `python -m pytest tests/signal` passes: 36 passed, 1 skipped, including the four new tests.
- `python -m pytest tests/signal tests/project tests/case` passes: 57 passed, 1 skipped.
- Not verified: the Vue changes (no `node_modules`, so no build or lint), and the migration itself (only checked for a single head, not applied to a database).
- `ruff format --check` flags a few pre-existing formatting issues in `models.py` and `test_signal_flow.py`. None are on lines I added, so I left them alone.

Nothing is committed.