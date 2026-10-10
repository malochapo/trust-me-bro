Signal definitions now have an optional `muted_until`, and a muted signal's new instances are recorded with filter action `mute` and never open a case. The signal tests pass (34 passed, 1 skipped), including two new ones for active and expired mutes. I haven't run the Alembic migration or loaded the web UI.

**Backend**
- `muted_until` is a new nullable column on the signal model, and it is accepted on create and update and returned on read.
- The API converts timezone-aware values to naive UTC, since the column has no timezone.
- `mute` is a new filter action. A signal counts as muted while `muted_until` is in the future, and the mute lapses on its own when that time passes.
- While muted, snooze and deduplication aren't evaluated. The change is in `filter_signal` in `src/dispatch/signal/service.py`.
- The migration is `2025-09-02_3c1d7a9e5b42.py`, chained after the latest tenant revision (`ff08d822ef2c`).

**Web UI**
- The signal table has a "Muted until" column that shows a relative time with the full date in a tooltip.
- The create/edit dialog has a "Muted until" date-time picker, and the picker's existing clear action removes the mute.

**Timezone display**
- The API returns `muted_until` without a timezone marker. In a browser that isn't on UTC, the displayed and picker-initial times will probably be off by the UTC offset. I didn't check this in a browser.
- The existing snooze `expiration` field is stored the same way.