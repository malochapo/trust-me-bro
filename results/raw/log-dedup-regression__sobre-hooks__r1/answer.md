The cause is a unit change in `filter_dedup`. Commit 9dc24f46, a "refactor" shipped on 2025-08-14, made the per-filter window count seconds instead of minutes.

- **Before the commit:** the per-filter lookback was `timedelta(minutes=f.window)`. A window of 120 meant 2 hours, which matches the earlier logs. Case 48222 on 08-13 and case 48489 on 08-14 kept absorbing GuardDuty signals for hours.
- **The commit:** it added `_window_start(seconds)` and changed the filter loop to `_window_start(f.window)` with a comment saying "SignalFilter.window is stored in seconds". The 120 stored for this signal is therefore now read as 2 minutes.
- **After the deploy:** the log shows the worker restarting at 20:05 on 08-14 with image `main-8298f999`, whose parent is 9dc24f46. From then on GuardDuty instances open new cases (48663, 48668, 48672, 48675, 48678) and only dedup within about 2 minutes.
- **Other signals:** the ones I saw don't use a configured deduplication filter. They either use the default window, whose `* 60` conversion keeps minutes, or are snoozed, so they are unaffected.

One thing I didn't settle: the `SignalFilter.window` column comment in `models.py` says seconds, with a default of `60 * 60`, which looks like the source of the commit's assumption. The old code and the UI value of 120 behaved as minutes, so the fix is to restore minutes. That means `_window_start(f.window * 60)`, or removing the commit's seconds interpretation.

I didn't check the `8298f999` image build itself beyond its commit ancestry, and I didn't make any changes.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds, so a window of 120 shrank from 2 hours to 2 minutes.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef