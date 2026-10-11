Muting is implemented end to end: `muted_until` is stored, accepted and returned by the API, shown in the table, and settable in the dialog. The mute filter runs before snooze and dedup and never opens a case. The 3 new service tests pass on PostgreSQL, and the signal suite passes apart from one failure that also occurs on clean `main`.

**What changed**
- **Model and migration:** `Signal.muted_until` is a nullable `DateTime`. The migration `2026-10-10_a3c1e9f0b7d2.py` (revision `a3c1e9f0b7d2`) chains onto the current head `ff08d822ef2c`.
- **API:** `muted_until` sits on `SignalBase`, so create, update, and read all carry it. Sending `null` on update clears the mute.
- **Filtering (`signal/service.py`):** a new `is_muted()` check runs first in `filter_signal`. If the mute is active, the instance gets `filter_action = mute` and snooze and dedup are skipped. The existing early return in `signal_instance_create_flow` then stops case creation.
- **Web UI:** a "Muted until" column in `Table.vue`, a date field in `NewEditDialog.vue` (reusing the filter dialog's `ExpirationInput`), and a "Muted" chip in `TableInstanceTriggers.vue`.

**Tests:** I added three tests to `tests/signal/test_signal_service.py`: a muted signal with a matching snooze filter gets `mute` and no case, an expired mute behaves normally, and `create()` stores `muted_until`.

**Failing test:** `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on clean `main` too, so it predates this change.

**Decisions to review**
- I added `mute` to the existing `SignalFilterAction` enum, which also makes it a valid value for a filter's `action`. It has no effect there, since snooze and dedup only look at their own actions. A separate enum would avoid this, but the spec asked for `mute` as a filter action.
- `muted_until` is stored as naive UTC, matching `expiration`. A non-UTC offset in the request would be stored as its wall-clock time.
- The signal stats endpoint counts muted instances as "alerted", because it only excludes `snooze`. I left that alone.
- The date picker's inner label reads "Expiration", since `ExpirationInput` hardcodes it. The field's own label is "Muted until".

**Not verified**
- The web UI is untested: there is no `node_modules` here, so I could not build or run it in a browser.
- The HTTP endpoints were not exercised directly.
- Nothing asserts that a muted instance opens no case through the full `signal_instance_create_flow`. That relies on the early return.
- Ruff reports a blank-line issue in `models.py` near the bottom. It is on `main` too and outside my edit.