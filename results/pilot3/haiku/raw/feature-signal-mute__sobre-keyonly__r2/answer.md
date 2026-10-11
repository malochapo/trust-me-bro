Ruff's remaining complaints are in code I didn't touch, plus a blank-line nit at the bottom of `models.py` that predates my edit. My new test code is clean.

## Summary

Signal definitions now have an optional `muted_until` timestamp. While it's in the future, new instances are stored with filter action `mute`, never open a case, and skip snooze and dedup. The mute ends on its own once the time passes.

**Backend**
- `src/dispatch/signal/models.py`: added `Signal.muted_until` (`DateTime(timezone=True)`, nullable), `muted_until` on `SignalBase` so it flows into create, update, and read schemas, and `SignalFilterAction.mute`.
- `src/dispatch/database/revisions/tenant/versions/2026-10-11_6d2b9e41c7a3.py`: adds the column, revising the existing head `ff08d822ef2c`. I checked that this is the only head.
- `src/dispatch/signal/service.py`: new `is_muted()`. `filter_signal` checks it first, sets `mute`, and skips snooze and dedup. Otherwise the existing logic runs unchanged.

**Web UI**
- `signal/Table.vue`: "Muted until" column, sortable, showing the formatted date or blank.
- `signal/NewEditDialog.vue`: "Muted until" `datetime-local` field in the main section. Its setter stores UTC ISO, and its getter converts back to local time for display.
- `signal/store.js`: `muted_until: null` added to the default selected state.

**Tests**
- `tests/signal/test_signal_service.py`: three new tests. A muted signal with a matching snooze filter gets `mute` and no case. A muted signal with an existing case in the same window does not dedup. An expired mute behaves normally.
- `python -m pytest tests/signal`: 35 passed, 1 skipped.

## Choices I made
- **Date picker:** I didn't reuse `DateTimePicker`. It formats for display in UTC but parses input as local time, so a saved value drifts by the browser's offset each time the dialog reopens. I used a native `datetime-local` input that converts explicitly. `ExpirationInput`'s shortcut buttons have the same offset problem for expirations, but I didn't change it.
- **`mute` is also a `SignalFilterAction`:** the enum is shared with instance `filter_action`, so the value is now valid on `SignalFilter` too. A filter with action `mute` would be accepted and do nothing. I didn't block it; say if you'd rather restrict it.

## Not verified
- **Frontend:** `node_modules` isn't installed, so I didn't run lint or a build. The Vue changes are unverified beyond reading them.
- **HTTP round trip:** I didn't exercise create or update over the API. The field is inherited through the schemas, and the DB-backed tests cover persistence.
- **Migration:** not run against a live database. The test fixtures build tables from the models.
- **Stats:** `get_signal_stats` counts any non-snooze instance as "alerted", so muted instances are counted as alerted. I left it alone because it wasn't in the request.