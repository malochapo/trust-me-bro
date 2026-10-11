The feature is in place across the database, API, filter logic and web UI. The signal test suite passes (35 passed, 1 pre-existing skip), but I could not build or lint the frontend because the repo has no `node_modules`.

**What changed**

- **Storage:** `Signal.muted_until` is a nullable `DateTime` column. The migration is `src/dispatch/database/revisions/tenant/versions/2026-10-11_81cfecb39875.py`, chained on the current head `ff08d822ef2c`. I checked that the chain has a single head.
- **API:** `muted_until` sits on `SignalBase`, so create and update accept it and reads return it. Sending `null` on update clears the mute.
- **Filtering:** `SignalFilterAction` gains `mute`. In `filter_signal`, a muted signal gets `filter_action = mute` and skips snooze and dedup entirely. `flows.py` already returns early on a filtered instance, so no case opens. The mute ends by itself: the check compares `muted_until` with the current time, so there is no background job.
- **Web UI:** a "Muted until" column in the signal definitions table, and a "Muted until" picker in the create/edit dialog (reusing `DateTimePickerMenu`). I added an "Unmute" button, because that picker has no clear control.
- **Tests:** three new tests in `tests/signal/test_signal_service.py`. One checks that an active mute skips a matching snooze filter. One checks that an expired mute is ignored. One checks the `muted_until` round trip through `update` and `SignalRead`, including clearing it.

**Choices I made**

- Stored times follow the existing `expiration` convention (naive UTC, read back as UTC). An update sent with a non-UTC offset is not normalised, so I'd add that if it matters.
- The mute check runs before snooze and dedup, so a muted instance is marked `mute` even if it would also have matched a snooze.

**Things to check**

- `mute` is now a valid `SignalFilter.action` as well, because both use the same enum. A filter with `action: mute` is accepted but does nothing. I left that alone; rejecting it at the filter schema is a small change if you want it.
- `black --check` flags `models.py` and two other test files, but it also flags them on the untouched baseline, so I didn't reformat them. Ruff passes on the changed Python.
- The Vue changes are unverified by a build or lint run.