**Root cause: commit `9dc24f46` changed the unit of the dedup window from minutes to seconds, so a 120 window now only looks back 2 minutes.**

The code path is `filter_dedup` in `src/dispatch/signal/service.py`. Before `9dc24f46`, it computed the lookback as `datetime.now(timezone.utc) - timedelta(minutes=f.window)`. The commit replaced that with `_window_start(f.window)`, and `_window_start` takes seconds. The added comment, "SignalFilter.window is stored in seconds", is what introduced the mismatch. The UI still labels the field "Window (minutes)" (`SignalFilterCreateDialog.vue`), and the stored `120` was entered in minutes. Other signals are unaffected because they have no custom deduplicate filter and take the default path, which was converted correctly (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`).

Evidence in the log: GuardDuty instances were deduplicated into case 48489 and later cases through 2025-08-14 ~15:08Z. The commit landed 2025-08-14 12:15 -0500 (17:15Z). After that, the GuardDuty signal opened case 48637 at 19:04Z, and later instances had to be checked against a window that was now 120 seconds. I could not match every GuardDuty event in the gap, so the timing is consistent with the commit but not a line-by-line confirmation.

Two things to check before fixing:
- `SignalFilter.window` is documented in `models.py` as seconds (default `60 * 60`), while the UI and the pre-commit code treated it as minutes. Existing rows were written by the UI in minutes, so the fix should keep minutes semantics (e.g. `_window_start(f.window * 60)`), not change stored data. Also, the schema default of `600` is ambiguous under either reading.
- I have not changed any code. This answer is the diagnosis only.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor in 9dc24f46 passes the filter's window (stored and entered in minutes) to `_window_start`, which expects seconds, so the lookback shrinks from 120 minutes to 120 seconds and GuardDuty instances no longer match the open case.
INTRODUCED_BY: 9dc24f46