Signal definitions now have an optional `muted_until`, and a muted signal's new instances are filtered with the new `mute` action. The signal tests pass (33 passed, 1 skipped), including one I added for muting. I didn't run the migration or try the UI.

- **Model and migration:** `Signal.muted_until` is a nullable `DateTime`, added by `2025-09-02_a7c3e91d5b24.py`, which follows the current head `ff08d822ef2c`. `SignalFilterAction` gained `mute`.
- **API:** `muted_until` is on the shared base schema, so it is accepted on create and update and returned on read. A timestamp with a timezone is converted to naive UTC before saving, matching how the column and the existing snooze check compare times.
- **Filtering:** `filter_signal` checks the mute first. If `muted_until` is in the future, it sets the instance's action to `mute` and returns, so snooze and deduplication filters never run. Once the time passes, the next instance is filtered normally.
- **UI:** the signal table has a sortable "Muted until" column, and the create/edit dialog has a datetime-local field. The dialog shows local time but sends UTC, and clearing the field unmutes the signal.
- **Test:** the new test, `test_filter_signal__muted`, covers an active mute and an expired one. It doesn't assert that no case is opened, because the test factory gives each instance a case up front.

I also didn't check whether anywhere else, such as signal stats or the instance filters in the UI, should treat `mute` as a known action.