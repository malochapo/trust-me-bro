Signal definitions now have an optional `muted_until`. While it's in the future, new instances are recorded with the `mute` filter action and never open a case. Snooze and deduplication aren't evaluated for them. The signal tests pass, including three new ones. I didn't run the migration or look at the UI in a browser.

- **Model and API:** `muted_until` is on the `Signal` model and the create, update and read schemas in `signal/models.py`. A timezone-aware value sent to the API is converted to naive UTC before it is stored, so an offset like `+02:00` isn't lost.
- **Filtering:** `filter_signal` in `signal/service.py` checks `muted_until` before anything else. Once the time passes, filtering goes back to normal on its own. `mute` is added to `SignalFilterAction`.
- **Migration:** `2025-09-02_a1c3e5f7b9d2.py` adds the nullable column. It follows the current tenant head, `ff08d822ef2c`.
- **Web UI:**
  - The signal definitions table has a sortable "Muted until" column, shown in local time.
  - The create/edit dialog has a datetime-local "Muted until" field that can be cleared. It converts between local time and UTC.
- **Tests:** muted instances get `mute`, an expired mute is ignored, and an update with an offset timestamp is stored as UTC. They're in `tests/signal/test_signal_service.py`.