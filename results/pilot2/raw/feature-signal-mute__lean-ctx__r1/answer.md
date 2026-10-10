Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are recorded with filter action `mute` and never open a case. `python -m pytest tests/signal` passes (34 passed, 1 skipped), including two new tests. I haven't run the Alembic migration against a database or opened the UI, and I haven't run the full test suite.

**Backend**
- **Model and filter:** `muted_until` is a nullable column on `Signal`, and `SignalFilterAction` has a new `mute` value in `signal/models.py`.
- **Migration:** `2025-09-02_a7c3e91d5b24.py` in the tenant revisions adds the column and chains from the current head `ff08d822ef2c`.
- **API:** `muted_until` is on the shared base schema, so it is accepted on create and update and returned on read. Timestamps with a timezone are converted to naive UTC, which matches how the column is stored.
- **Filtering:** at the top of `filter_signal` in `signal/service.py`, if `muted_until` is in the future the instance gets `mute` and the function returns early. Snooze and deduplication filters are not evaluated. Once the time passes, filtering behaves as before, so nothing needs to clear the field.
- **Tests:** `test_filter_actions_mute` also attaches an active snooze filter and checks the result is still `mute`. `test_filter_actions_mute_expired` checks a past `muted_until` is ignored.

**Web UI**
- **Table:** `signal/Table.vue` has a "Muted until" column that shows a relative time with the full date in a tooltip.
- **Dialog:** `signal/NewEditDialog.vue` has a "Muted until" field. It reuses the existing `ExpirationInput` from the snooze filter dialog, which includes the quick-pick shortcuts like 1 hr and 1 day. `signal/store.js` has the default for the new field.