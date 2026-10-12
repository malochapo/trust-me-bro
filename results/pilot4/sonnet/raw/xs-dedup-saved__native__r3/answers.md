Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs and today's `src/dispatch/signal/service.py`. I did not run any code or tests.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns immediately when the incoming instance is a canary.
- Both dedup queries now exclude canary instances with `~SignalInstance.canary`. That covers the default no-filter query and the per-filter query.
- It adds no time window.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- This is the window used when a signal has no filters at all. It was a hard-coded `timedelta(hours=1)`.
- It is now read from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`. The setting is an int with a default of **45 minutes**, so the default dropped from 60 to 45 minutes.
- In that case the instance joins the most recent non-canary instance of the same signal that already has a case.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- It removed the "no mode" and "no action" warnings and merged the active-mode and snooze-action checks into one condition.
- It also changed one behaviour, though the message calls it a simplification. An expired snooze filter (`expiration <= now`) used to `continue` to the next filter. It now does `break`, so the loop stops and later snooze filters on that signal are not checked. This looks like an unintended side effect.
- A snooze filter with no expiration is still skipped with a warning.
- The snooze window is the filter's `expiration` datetime, not a duration. A filter with no expression snoozes every instance of the signal.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It added `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
- The default window is now computed as `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes (2700 s) and gives the same result as before.
- The per-filter window changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`. `f.window` is therefore now read as **seconds**, which matches the column definition (`Integer`, default `60 * 60` seconds, i.e. 1 hour) in `models.py`.
- Before this commit the value was treated as minutes, so a default 3600 meant 3600 minutes (60 hours). Despite the "refactor" label, this changes behaviour for dedup filters.
- The pydantic schema default is `window: int | None = 600`, which is 10 minutes in seconds.

**Values applied today**

| Case | Value |
|---|---|
| Signal with no filters (default dedup) | 45 minutes (configurable) |
| Dedup filter window (`SignalFilter.window`) | seconds; column default 3600 s (1 hour); schema default 600 s (10 minutes) |
| Snooze | until the filter's `expiration` timestamp (UTC) |

The `filter_signal` docstring still says the default is a "1-hour window". That is stale, since the default is 45 minutes.

Other signal commits in the range (`4474af25` outcome logging, `d2675cf4` field masking, and the UI and stats commits) don't touch the snooze or dedup decision.

----- next turn -----

I saved the findings to memory in `signal-snooze-dedup-history.md` and added a line for it to `MEMORY.md`. The note has the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`) with what each changed and the window values and units. It also records two follow-ups I noticed but haven't acted on: the stale "1-hour" docstring on `filter_signal`, and the `continue` → `break` change in `filter_snooze`. No code was changed.

----- next turn -----

Deduplication windows are fixed. The filter's `window` is read as minutes again, which is what the UI shows, so existing filters work without edits.

**Cause:** commit `917a0b7b`, "refactor(signal): share the lookback window computation" from 2025-08-14. It changed the per-filter lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which reads the value as seconds. A window of 30 became 30 seconds, so two instances ten minutes apart no longer deduplicated. The existing stored values were entered in minutes, so no data migration is needed.

**Changes:**
- `src/dispatch/signal/service.py`: the filter window is now `_window_start(f.window * 60)`. I also corrected the stale "1-hour window" text in the `filter_signal` docstring.
- `src/dispatch/signal/models.py`: the column default is now 60, and the schema default is now 10. Both are in minutes, the same durations as before (1 hour and 10 minutes), but in the unit the code now reads.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. A 10-minute-old instance must deduplicate into a 30-minute-window filter's case. It fails on the old code and passes on the new.

All of `tests/signal` passes: 33 passed, 1 skipped.

The existing dedup tests didn't catch this. In the one I debugged, the filter never actually attached to the signal, so it exercised only the default 45-minute window. The other tests that use the same filter setup may have the same problem; I didn't check them.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES