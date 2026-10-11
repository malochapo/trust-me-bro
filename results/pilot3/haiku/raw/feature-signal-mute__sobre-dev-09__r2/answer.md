Signal definitions now have an optional `muted_until`. While it's in the future, new instances are recorded with filter action `mute`, never open a case, and skip snooze and dedup. The signal tests pass (35 passed, 1 skipped, including 3 new mute tests). I could not build or run the web UI, so the Vue changes are unverified.

**Backend**
- `models.py`: `Signal.muted_until` is `DateTime(timezone=True)`, and `SignalBase` exposes it, so create, update, and read all carry it. `SignalFilterAction` gains `mute`.
- `service.py`: a new `is_muted()` helper, and `filter_signal` sets `mute` and skips snooze and dedup when the signal is muted. The mute ends by comparison with the current time, so no background job is needed. `get_signal_stats` now counts `mute` as not alerted.
- Migration `2026-10-10_2f1df446f7d6.py` adds the column with `down_revision = ff08d822ef2c`. That is the only head. I checked the SQL offline; I did not run it against a database.

**Web UI**
- `Table.vue`: a sortable "Muted until" column, shown blank when unset.
- `NewEditDialog.vue`: a "Muted until" `datetime-local` field. It converts the local value to a UTC ISO string on save, and back on load.
- `store.js`: `muted_until: null` in the default selected state.

**Decisions you may want to change**
- `mute` is added to the shared `SignalFilterAction` enum, so the API will also accept it as a `SignalFilter.action`. A snooze or dedup filter with that action does nothing. I could reject it at the filter level if you prefer.
- A muted instance is stored with no case and `filter_action = mute`.

**Not verified**
- The web app has no `node_modules`, so I could not compile the Vue changes. Please run the frontend build before merging.
- Ruff format reports a pre-existing hunk in `models.py`, which I left alone.

**Existing issue, not changed**
- Deduplication can match a snoozed or muted instance that has no case, which can leave the new instance without a case. Snoozed instances already had this problem, so I did not change it.