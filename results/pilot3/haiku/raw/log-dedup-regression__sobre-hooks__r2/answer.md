**Root cause:** commit `9dc24f46` ("refactor(signal): share the lookback window computation") changed how a deduplication filter's window is read. It used to be `timedelta(minutes=f.window)`. The refactor now calls `_window_start(f.window)`, and `_window_start` takes seconds. So the stored 120 is read as 120 seconds (2 minutes) instead of 120 minutes. The same commit multiplies the default window by 60 (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`), which is why only filtered signals broke. The other signals use the default path and are fine.

**Evidence from the log:**
- Before the commit landed (2025-08-14 ~17:15Z, 12:15 -0500), GuardDuty dedup behaved as a 120-minute window. For example, a new case at 10:58Z was followed by dedup hits at 11:03Z and 12:07Z, and the next new case came at 14:11Z, after a gap of over 2 hours.
- After the commit, the same signal opened a new case 1h52m after the last dedup hit (19:50Z → 21:42Z). Under a 120-minute window that should have been deduplicated. It then opened new cases 10 minutes apart (21:42Z → 21:52Z → 21:56Z → 22:02Z → 22:13Z), which is what a 2-minute window produces.

I did not edit anything. Two things to decide before fixing:
- The fix I'd recommend is `_window_start(f.window * 60)`, which keeps the minutes semantics that the UI (dropdown values 5–30) and the pre-refactor code both use.
- `models.py` has a comment saying `window` is in seconds (default `60 * 60`), and the `SignalFilterBase` schema default is `600`. Those two disagree with the UI, so the unit should be fixed in the model comment as well. If you decide seconds is the true unit, the fix goes the other way: the UI would need to convert, and the stored 120 would need migrating.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor in 9dc24f46 passes the per-filter `f.window` (stored as minutes, as the UI and the pre-refactor code treat it) straight into `_window_start`, which expects seconds, so the 120-minute window is applied as 120 seconds.
INTRODUCED_BY: 9dc24f46