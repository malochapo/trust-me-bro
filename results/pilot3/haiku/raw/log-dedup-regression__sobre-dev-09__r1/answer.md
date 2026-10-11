**Root cause:** commit `9dc24f46` changed how the deduplication window is converted to a time, from minutes to seconds. Stored `window` values of 120 are now a 2-minute lookback instead of 2 hours, so GuardDuty instances that arrive a few minutes apart no longer find the open case.

**Evidence**

- **Before the commit**, `filter_dedup` computed the cutoff as `timedelta(minutes=f.window)`. GuardDuty deduplicated across gaps of 10 to 40 minutes on 08-13 and early 08-14 (e.g. 2025-08-14T10:58:42 created case 48563, then 11:03:27 and 11:11:25 deduplicated into it).
- **After the commit** (`service.py:845-847`), the cutoff is `_window_start(f.window)`, which subtracts `f.window` seconds. The 08-15 entries match a 120-second window: 00:36:08 and 00:39:24 each created a new case three minutes apart, while 00:39:51 deduplicated into 00:39:24 about 27 seconds later.
- **Other signals were not affected**: the default-window branch still multiplies `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60, so only custom filters changed behaviour.

**Caveats**

- The "seconds" convention is not new in this commit. The model comment at `src/dispatch/signal/models.py:206-208` (default `60 * 60`) says seconds and dates from `ecbad47f`. What the commit changed is the interpretation of existing stored values. Before it, the code treated them as minutes.
- The UI's `windows` list in `SignalFilterCreateDialog.vue:196` offers 5–30, not 120, and I did not find a unit conversion on submit. So I can't confirm whether the stored 120 was entered as minutes. If it was, the commit broke it. If the filter really holds seconds, the old code was the one that was wrong for it. Either way the regression starts with this commit, and the fix needs a decision on which unit the stored values use.
- The log flip is not clean. GuardDuty still deduplicated at 19:15Z on 08-14, about 10 minutes after the 17:15Z commit, which a 2-minute window would not explain, though a sibling instance I can't see in the log could account for it.

I did not change any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The custom-filter branch now passes `f.window` (a value treated as minutes before) to `_window_start`, which treats it as seconds, shrinking a 120-minute lookback to 120 seconds.
INTRODUCED_BY: 9dc24f46 (9dc24f4634eb895b3d98b168e931306c3131dfef)