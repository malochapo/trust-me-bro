The root cause is commit `9dc24f46`, which changed how `filter_dedup` converts a filter's `window` value. Filter windows entered in the UI are minutes, so the old code did `timedelta(minutes=f.window)`. The refactor passes the same raw value to `_window_start`, which treats it as seconds. A window of 120 went from 2 hours to 2 minutes, and GuardDuty alerts arrive more than 2 minutes apart, so they stop matching the open case.

Evidence:
- **Logs:** GuardDuty signals joined existing cases throughout 2025-08-13 with gaps of up to about 20 minutes between them (e.g. case 48353 at 13:31, 13:35, 13:36, 13:48, 13:55, 14:07, 14:15). From 2025-08-14 on, nearly every GuardDuty alert creates a new case. The first post-refactor creations are at 19:04Z and 21:42Z on 08-14 (the commit is 12:15 -0500, i.e. 17:15Z).
- **Diff:** `9dc24f46` replaced `timedelta(minutes=f.window)` with `_window_start(f.window)` and added the comment "SignalFilter.window is stored in seconds". Nothing converts the stored value, so the existing value of 120 now means seconds.
- **UI:** `SignalFilterCreateDialog.vue` offers window choices of 5–30 and sends the value unconverted, so the UI treats the window as minutes. The model comment in `src/dispatch/signal/models.py` (`# number of seconds`) dates from 2022, so the commit's "stored in seconds" comment conflicts with how the UI and operators use the field.
- **Other signals:** The default-window path already multiplies by 60 and is unaffected. Any other signal with a deduplicate filter would be affected too, but the report only mentions this one.

I did not change any code. The likely fix is to restore minutes semantics in `filter_dedup` (for example `_window_start(f.window * 60)`), or else convert existing stored windows and fix the UI and model together. Confirm which unit the stored data really uses before choosing.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The filter window, which the UI stores and operators set in minutes, is passed unconverted to `_window_start` (seconds), shrinking a 120-minute dedup window to 120 seconds.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef