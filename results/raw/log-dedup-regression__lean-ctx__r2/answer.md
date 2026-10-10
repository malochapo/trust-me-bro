The cause is commit 9dc24f46, a refactor that changed the deduplication window from minutes to seconds.

- **Logs:** Before 2025-08-14 the GuardDuty signal produced one case and then long runs of `filtered: action=deduplicate`. For example, case 48222 absorbed instances for about 3 hours. After the change, `created case` lines show up every few minutes. The log has 54 "created case" lines for this signal.
- **Code:** `filter_dedup` in `src/dispatch/signal/service.py` used to compute the window as `timedelta(minutes=f.window)`. Commit 9dc24f46 (2025-08-14, "refactor(signal): share the lookback window computation") added `_window_start(seconds)` and switched this call to `_window_start(f.window)`. That call now treats `f.window` as seconds.
- **Effect:** A filter window of 120 now means 120 seconds instead of 120 minutes. Instances arriving a few minutes apart fall outside the window and each opens a new case.
- **Other signals:** They either have no filter or have windows long enough that this isn't noticeable. The default-window branch was converted correctly with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`.
- **Ambiguity:** The `SignalFilter.window` column comment in `src/dispatch/signal/models.py` says "number of seconds", and the commit's inline comment repeats that. But the old code, the UI value of 120 and the logs all treat it as minutes. I did not check the UI source to confirm the unit it saves. The likely fix is to restore minutes with `_window_start(f.window * 60)`.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor replaced `timedelta(minutes=f.window)` with `_window_start(f.window)`, which treats the filter's window as seconds, so a window of 120 shrinks from 120 minutes to 120 seconds and later signals no longer deduplicate into the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef