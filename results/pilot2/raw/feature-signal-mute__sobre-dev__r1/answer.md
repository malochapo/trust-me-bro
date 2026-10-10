Signal definitions now have an optional `muted_until`. While it's in the future, new instances are saved with filter action `mute` and never open a case. `python -m pytest tests/signal` passes (34 passed, 1 skipped). I did not run the migration or load the web UI.

**Backend**
- **Model and API:** `muted_until` is a nullable `DateTime` on `Signal` and is part of the shared base schema, so create, update and read all carry it. `SignalFilterAction` gains `mute`.
- **Filtering:** a new `filter_mute` in `signal/service.py` runs first in `filter_signal`. If the signal is currently muted, snooze and deduplication are skipped entirely. Once the time passes, filtering behaves as before, so the mute ends on its own with nothing to clean up.
- **Migration:** `database/revisions/tenant/versions/2025-09-02_3c1a5e7d9b42.py` adds the column, chained after the current head `ff08d822ef2c`.
- **Tests:** two new tests in `tests/signal/test_signal_service.py`, one for an active mute and one for an expired mute.

**Web UI**
- **Table:** there is a "Muted until" column in `signal/Table.vue`.
- **Dialog:** the create/edit dialog in `NewEditDialog.vue` has a "Muted until" field. I reused the existing `ExpirationInput` from the snooze filter dialog, so it comes with the same quick shortcuts (5 min, 1 hr, 1 day and so on) and a clear button.
- **Store:** `store.js` has the new default field.

**Things to know**
- `muted_until` is stored without a timezone and read as UTC, like the existing filter `expiration`.
- The UI shows `mute` as "Not Filtered" in the instance status chip, because `TableInstanceTriggers.vue` only knows snooze and deduplicate. I left that unchanged since you didn't ask for it. Adding a "Muted" label there is a small change if you want it.
- The signal stats query counts only snoozed instances separately, so muted ones fall into the non-snoozed bucket.