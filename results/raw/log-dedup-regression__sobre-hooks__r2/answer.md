The cause is a unit change in a refactor: the per-filter dedup window was converted from minutes to seconds, so your window of 120 now means 2 minutes instead of 2 hours.

**What the logs show**
- Until about 19:50Z on 2025-08-14, GuardDuty signals deduplicate normally. For example, case 48637 collects instances arriving 6 to 12 minutes apart.
- At 20:05:12Z on 2025-08-14 the worker restarted on image `main-8298f999`, which contains commit `9dc24f46`. The previous image, `main-3e290034`, does not contain it.
- After the restart, the GuardDuty signals create a new case almost every time (48663, 48668, 48672, 48675, 48678). Dedup only fires when two instances arrive within about a minute (e.g. 21:56:23Z then 21:56:42Z).

**The code**
Commit `9dc24f46` ("refactor(signal): share the lookback window computation") changed `filter_dedup` in `src/dispatch/signal/service.py`.
- Before, the filter window was `timedelta(minutes=f.window)`.
- After, it is `_window_start(f.window)`, and the new helper does `timedelta(seconds=seconds)`.
- The commit added the comment "SignalFilter.window is stored in seconds". That matches the model comment in `src/dispatch/signal/models.py` and its 3600 default. But the existing filter values were evidently entered as minutes, so 120 now means 120 seconds.
- The default no-filter path was converted correctly (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`). That is why signals without a custom filter still deduplicate.
- I did not find where the UI labels the unit, so I'm inferring minutes from the behaviour before and after the change.

Fixing it means restoring minutes in the filter path, or migrating the stored values if seconds is the intended unit.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which uses seconds, so a stored window of 120 shrank from 2 hours to 2 minutes and later signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef