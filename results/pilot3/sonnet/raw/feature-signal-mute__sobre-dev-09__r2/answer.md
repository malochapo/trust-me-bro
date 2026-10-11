Signal definitions now have an optional `muted_until`. While it is in the future, every new instance of that signal is recorded with `filter_action = "mute"` and never opens a case. The signal tests pass, including two new ones for an active and an expired mute. I did not run the Alembic migration or the web UI.

- **Mute behaviour:** `filter_signal` checks `muted_until` first. If it is still in the future, it sets `mute` and returns, so snooze and deduplication filters are not evaluated. Once the time passes, filtering goes back to normal on its own.
- **Storage:** the column is a naive UTC `DateTime`, with the migration in `2025-09-02_a7c3e91d5b24.py` (revises `ff08d822ef2c`).
- **API:** `SignalBase` now carries `muted_until`, so create, update and read all accept and return it. A timezone-aware value sent by a client is converted to naive UTC before it is stored.
- **UI table:** the signal definitions table has a "Muted until" column that shows a relative time, with the full date in a tooltip.
- **UI dialog:** the create/edit dialog has a datetime-local field that shows local time and sends UTC. Clearing it unmutes the signal.