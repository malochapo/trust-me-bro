The root cause is a unit mismatch introduced by commit 9dc24f46. It changed how the deduplication window of a signal filter is interpreted, from minutes to seconds.

- **Before the commit:** `filter_dedup` in `src/dispatch/signal/service.py` computed the lookback as `timedelta(minutes=f.window)`. A window of 120 meant 120 minutes. The log shows this working on 2025-08-13 and until about 2025-08-14 19:04. Cases for this signal were created roughly every 3–5 hours and everything in between was logged as `action=deduplicate`.
- **After the commit:** the lookback goes through a new helper, `_window_start(f.window)`, which treats the value as seconds. A window of 120 now means 2 minutes. Instances arriving more than 2 minutes after the open case no longer match it and open a new case. The log shows case creation speeding up from 2025-08-14 21:42, with new cases about 10 minutes apart.
- **Other signals:** they presumably use the default window or a filter whose configured value is larger.
- **Stored unit:** `SignalFilter.window` in `models.py` is commented as "number of seconds", which is what the refactor assumed. But the UI value 120 was evidently entered, and worked, as minutes. The stored data and the earlier behaviour disagree with that comment, so the refactor silently changed what existing filters mean.
- **Not checked:** I did not confirm that 9dc24f46 was deployed at the moment the behaviour flipped. The commit is dated 2025-08-14 12:15 -0500, which fits the log.

The default-window branch is fine. It multiplies `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60 before passing it to the helper.

The fix is to pass `f.window * 60` to `_window_start` (or confirm the unit the UI saves and correct either the code or the model comment to match).

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor replaced `timedelta(minutes=f.window)` with `_window_start(f.window)`, which treats the value as seconds, so a filter window of 120 shrank from 120 minutes to 120 seconds and later instances no longer matched the open case.
INTRODUCED_BY: 9dc24f46