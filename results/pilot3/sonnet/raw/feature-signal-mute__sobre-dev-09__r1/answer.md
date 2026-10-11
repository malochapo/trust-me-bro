Signal definitions now have an optional `muted_until`, and a muted signal's new instances are recorded with filter action `mute` and never open a case. The signal tests pass (33 passed, 1 skipped), including a new one for muting. I haven't run the migration or looked at the UI in a browser.

- **Filtering:** the `mute` check in `filter_signal` (`signal/service.py`) runs before the snooze and deduplication filters, so they are skipped while a signal is muted. The mute ends by itself once the timestamp passes, with no job needed. Timestamps with no timezone are read as UTC.
- **Storage and API:** `muted_until` is a nullable `DateTime` column on `Signal`, added by a new migration `2025-09-02_3c1d5a7e9b24.py` on top of `ff08d822ef2c`. It is part of the base signal schema, so it is accepted on create and update and returned on read.
- **Table:** a "Muted until" column shows an active mute as a warning chip and an expired one as "Expired <date>". The column is sortable.
- **Dialog:** the signal create/edit dialog has a "Muted until" field, using the existing `ExpirationInput` date picker.

Two caveats:
- **Time zone in the UI:** the API returns the timestamp without a timezone, so the browser reads it as local time. The same applies to other timestamps shown by `formatDate`.
- **Sorting:** the sort option is declared on the column, but I didn't check that the backend sort handles `muted_until`.

The test is in `tests/signal/test_signal_service.py`.