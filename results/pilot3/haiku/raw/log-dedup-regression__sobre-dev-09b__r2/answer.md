The root cause is commit `9dc24f46`, which changed how the filter window is read. The UI stores the window in minutes, but the code now reads it as seconds.

**What changed:** The commit `9dc24f46` ("refactor(signal): share the lookback window computation", 2025-08-14 12:15 -0500) replaced `timedelta(minutes=f.window)` with `_window_start(f.window)`. `_window_start` takes seconds, and the new comment says `SignalFilter.window` "is stored in seconds". But the filter dialog (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue`, offering 5–30) sends the raw value with no conversion, so its values are still minutes. Your GuardDuty filter's 120 used to mean a 120-minute lookback. After the commit it means 120 seconds, which is 2 minutes.

**Why it fits the logs:** Before 2025-08-14, GuardDuty instances arriving 7–20 minutes apart were deduplicated into one case (e.g. case 48222 across 2025-08-13 00:51–01:49). From 2025-08-14 02:55 onward, each GuardDuty instance creates a new case, because the previous one is always more than 2 minutes old. Datadog, Okta, and Cloudflare signals fire every minute or so, so the 2-minute window still catches them, which is why only GuardDuty looks broken.

**Fix (not applied):** Restore the minutes conversion for the filter branch, e.g. `window = _window_start(f.window * 60)`, or change the dialog and model to store seconds consistently. The model's `window` default of `60 * 60` (in `models.py`) suggests the seconds contract was intended. Whichever you choose, existing filter rows need checking, since their stored values are in whatever unit was written before.

Root cause at the code level: `filter_dedup` in `src/dispatch/signal/service.py` passes the stored filter window straight to `_window_start` as seconds, while stored values are minutes.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The lookback window stored in minutes by the UI is now passed to `_window_start` as seconds (after commit 9dc24f46), so a 120-minute window shrinks to 2 minutes and GuardDuty instances no longer match the existing case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef