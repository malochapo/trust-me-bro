Signal definitions now have an optional `muted_until` timestamp. While it's in the future, new instances get the `mute` filter action and never open a case. I ran the signal tests and four new ones pass, but the frontend is not built or rendered and the migration isn't run against a real database.

**What changed**

- **Backend behavior** (`src/dispatch/signal/service.py`): `filter_signal` checks `is_signal_muted` first. A muted signal sets `filter_action = mute` and skips snooze and dedup. The flow already returns early on any filtered instance, so no case is created. The mute ends on its own because the check compares against the current time.
- **Model and API** (`src/dispatch/signal/models.py`): `muted_until` is a `DateTime(timezone=True)` column, and `SignalBase` exposes it, so create, update and read all carry it. Sending `null` on update unmutes the signal.
- **Migration**: `src/dispatch/database/revisions/tenant/versions/2026-10-10_4e2827c67d82.py`, revising the previous head `ff08d822ef2c`.
- **Table** (`signal/Table.vue`): a "Muted until" column showing "Not muted" or a relative date with the full date in a tooltip.
- **Dialog** (`signal/NewEditDialog.vue`, `signal/store.js`): a `DateTimePickerMenu` in the browser's timezone, with an Unmute button.
- **Instance status chip** (`signal/instance/TableInstanceTriggers.vue`): shows "Muted" instead of the misleading "Not Filtered".

**Choices I made**

- I used a timezone-aware column rather than the naive `DateTime` the existing `expiration` uses, because the naive form silently drops offsets from API input.
- `mute` is added to the shared `SignalFilterAction` enum, which is how instance `filter_action` is typed. That also makes `mute` accepted as a `SignalFilter` action, where it would be silently ignored. I left that alone; rejecting it at the filter schema would be a small follow-up.

**Tests**

- New tests: two for mute precedence and expiry in `tests/signal/test_signal_service.py`, one for create/update round-tripping `muted_until` including unmuting, and one flow test in `tests/signal/test_signal_flow.py` asserting no case is created.
- `python -m pytest tests/signal tests/database`: 60 passed, 1 skipped, 1 failed. The failure is `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, which also fails on the untouched tree.
- `black --check` flags two files, `models.py` and `test_signal_flow.py`; the untouched tree is flagged for the same two files, so I didn't add new formatting issues.

**Not verified or not done**

- The Vue changes are unverified: `node_modules` isn't installed, so I could not build or lint them, and I did not check the UI in a browser.
- The migration is only checked to be the single Alembic head; I did not run it against a database.
- Muted instances still count as "alerted" in the signal stats, which I left alone.
- Changes to `muted_until` don't appear in the signal's history log, because the update path skips datetime fields.
- The filter docs under `docs/` don't mention muting.