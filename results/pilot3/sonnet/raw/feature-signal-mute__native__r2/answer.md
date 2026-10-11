You can now mute a signal definition until a given time, and the mute ends on its own when that time passes. The signal tests pass, including two new ones for muting, but I haven't run the web UI or the migration.

One other test fails, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`. It fails the same way with my changes stashed.

- **Filtering:** a new `mute` filter action. In `filter_signal`, a signal whose `muted_until` is still in the future gets its instance marked `mute` and returned as filtered, so no case opens. Snooze and dedup are skipped. Once `muted_until` has passed, filtering behaves as before. The check is in a new `is_muted` helper in `signal/service.py`.
- **Storage and API:** `muted_until` is a nullable column on `Signal`, added with the migration `2025-09-02_a7c3e91d5b24.py`, which follows `ff08d822ef2c`, the previous head. It is also on the shared signal schema, so create, update and read all carry it.
- **UI:**
  - The signal definitions table has a sortable "Muted until" column.
  - The create/edit dialog has a "Muted until" field. It reuses the existing `ExpirationInput` from the snooze dialog, so it comes with the same quick-pick shortcuts such as "1 day" and "7 days".
- **Time zones:** the column is stored without a time zone and read as UTC, the same as snooze expirations. The expiration picker produces local-time strings, so a mute set from the UI may end earlier or later than intended by the browser's UTC offset. Snooze has the same quirk today and I didn't change it.