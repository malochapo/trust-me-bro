**Root cause:** commit `9dc24f46` changed how the custom dedup filter's lookback window is converted, so a window of 120 is now read as 120 seconds instead of 120 minutes.

- **Before the commit**, the filter path computed `datetime.now(timezone.utc) - timedelta(minutes=f.window)`, which matched the UI. The UI's "Window (minutes)" dropdown (`SignalFilterCreateDialog.vue`, values 5–30) stores minutes.
- **After the commit**, the same path calls `_window_start(f.window)`, which subtracts `f.window` seconds. The new comment says "SignalFilter.window is stored in seconds", which matches the model column comment from 2023 (`models.py:208`) but not what the UI writes.
- Only signals with a custom `deduplicate` filter go through this line. Signals with no filters use the default path, which multiplies `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60 and is unaffected. That fits the report that other signals look fine.

**Caveat on the logs:** the timing doesn't fully confirm this. The commit landed at 2025-08-14 17:15 UTC, but GuardDuty creates appear from 02:55 UTC that day. Some dedups also join cases after gaps of about 10 minutes, which a 2-minute window should not allow. The log data is noisy, so treat the commit as the code-level cause and confirm by checking the stored `signal_filter.window` value for the GuardDuty filter and the worker's deploy time.

**Suggested fix:** keep the UI's minutes contract and convert explicitly in `filter_dedup`, e.g. `_window_start(f.window * 60)`, or change the stored unit everywhere, including the model comment and any existing rows. Either way, the window used by the default path and the filter path should share one unit.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The custom-filter lookback now passes the stored window (entered in minutes in the UI) to `_window_start`, which treats it as seconds, so a 120-minute window becomes 2 minutes and most repeat GuardDuty signals open new cases.
INTRODUCED_BY: 9dc24f46