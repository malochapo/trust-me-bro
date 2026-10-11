The root cause is commit `9dc24f46` ("refactor(signal): share the lookback window computation", 2025-08-14). It changed how custom deduplication filters read their `window` value, so the GuardDuty filter's 120 is now treated as 120 seconds instead of 120 minutes.

**What changed**

- Before the commit, `filter_dedup` computed the custom-filter lookback as `now - timedelta(minutes=f.window)`.
- The commit replaced that with `_window_start(f.window)`, and `_window_start` takes seconds. The comment it added says `SignalFilter.window is stored in seconds`.
- The model default (`SignalFilter.window`, `models.py` ~L206) is documented as seconds, so the refactor matches the model. But the UI's dialog labels the field "Window (minutes)" and offers 5–30. A filter saved as 120 under that label was meant as 120 minutes, so the refactor silently shrank every existing custom window by 60×.
- For GuardDuty, the window is now 2 minutes. An instance only joins the open case if the previous matching instance arrived within the last 2 minutes.

**Evidence in the log**

- From 2025-08-13 through 2025-08-14 the GuardDuty instances always join the existing case, and the gaps between instances were sometimes over 2 hours. Those gaps never created a new case, which is expected for a 120-minute window.
- The first new case after a short gap appears at 2025-08-14T21:52Z, 10 minutes after the previous instance. From then on, new cases keep appearing after gaps of 3–12 minutes, which is the 2-minute window at work.
- Other signals don't show this because they use the default one-hour rule (`if not signal_instance.signal.filters` branch), which this commit did not change.
- The commit landed at 17:15Z; the first visible failure in the logs is about 4.5 hours later. I'm reading that as a deploy lag, but I haven't checked the deploy history.

**Fix options (not applied)**

- Restore the minutes interpretation in `filter_dedup`: `window = datetime.now(timezone.utc) - timedelta(minutes=f.window)`.
- Or keep seconds and migrate the stored `SignalFilter.window` values by multiplying by 60, and fix the UI label and options to match. This is the cleaner long-term choice if the model's seconds contract is the intended one.

Either way, it's a unit mismatch between the stored value, the UI label, and the code; the refactor is where it became visible.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the custom-filter lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the stored window as seconds, so the UI's minute-labelled 120 now means a 2-minute window.
INTRODUCED_BY: 9dc24f46