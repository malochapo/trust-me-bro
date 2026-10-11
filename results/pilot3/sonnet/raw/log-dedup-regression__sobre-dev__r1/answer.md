The root cause is a unit mix-up introduced by commit `9dc24f46`, which made the deduplication window 60 times shorter than configured.

- **The change:** that refactor moved the window calculation into a new helper, `_window_start(seconds)`. In `filter_dedup`, the signal's own filter window used to be passed to `timedelta(minutes=f.window)`. It is now passed to the helper as `_window_start(f.window)`, so it is read as seconds. The comment added with it ("stored in seconds") matches the model column comment but not the UI, which labels the field "Window (minutes)".
- **Effect on this signal:** a filter value of 120 now means 2 minutes instead of 120 minutes.
- **Why other signals look fine:** the default-window branch was converted correctly, using `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, so signals without a custom filter are unaffected. Signals with a custom filter window would also be affected. Your logs only show the GuardDuty signal being checked in detail.
- **Log evidence:** the `GuardDuty: Unauthorized API call` signal had one new case every 3–5 hours, with a run of dedup hits after each (for example case 48489, then 48523, then 48563). The deploy of image `main-8298f999` (pod `tlmhd`, 2025-08-14T20:05Z) contains `9dc24f46`. From about 21:42Z that evening the signal opens several new cases within minutes, and the log has no further deduplication lines for it after that.
- **Not fully resolved:** I did not run the code. Two things in the repo disagree about the units: the `SignalFilter.window` column comment says seconds, and the UI label says minutes. The behaviour change after the deploy fits the units being misread, but the intended unit is a call for the team to make. The simplest fix is `_window_start(f.window * 60)`, which restores the previous behaviour.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: After the refactor, filter_dedup passes the filter's window (entered in minutes in the UI, e.g. 120) to `_window_start(seconds)`, so the dedup lookback shrinks from 120 minutes to 120 seconds and new signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef