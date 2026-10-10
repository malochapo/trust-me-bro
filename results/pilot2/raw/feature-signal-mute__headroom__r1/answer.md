Signal definitions now have an optional `muted_until` timestamp, and a muted signal's new instances are filtered with the new `mute` action and never open a case. The signal tests pass (34 passed, 1 skipped), including two new ones for a muted and an expired mute. I haven't run the Alembic migration or opened the UI, so those parts are untested.

- **Model and API:** `muted_until` is a nullable column on the signal. It is accepted on create and update and returned on read. Timestamps with a timezone are converted to UTC before saving, because the column stores naive UTC.
- **Filtering:** `filter_signal` in `src/dispatch/signal/service.py` checks the mute first. If `muted_until` is in the future, it sets the filter action to `mute` and returns right away. Snooze and deduplication are skipped, and the instance is still recorded. Once the time passes, filtering behaves as before.
- **Migration:** `2025-09-02_a7c3e91d5b24.py` in the tenant versions adds the column. It follows `ff08d822ef2c`, the latest revision.
- **UI:** the signal definitions table has a sortable "Muted until" column showing a relative time, with the full date in a tooltip. The create/edit dialog reuses the existing expiration picker used for signal filters, labelled "Muted until".

`ruff` isn't installed here, so I didn't run the formatter.