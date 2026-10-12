Three commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, and a fourth only touches canary handling. I read the diffs and the current code in `src/dispatch/signal/service.py`. I changed no code.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early, with no deduplication, when the incoming instance is a canary.
- Both dedup queries now exclude canary instances from the candidates: the default no-filter query and the per-filter query.
- It adds no time window and changes none.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The window for signals with no filters was hard-coded at `timedelta(hours=1)`. It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
- **Value today:** 45 minutes by default, overridable by environment variable. The default changed from 60 minutes to 45.
- In that case, any non-canary instance of the same signal from that window that already has a case makes the new instance a duplicate. It joins that case.
- The docstring of `filter_signal` still says "1-hour window", which is now stale.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- It dropped the separate "no mode" and "no action" warning branches and merged them into one check: `mode != active or action != snooze` means skip.
- It also changed one behavior, despite the refactor label. A snooze filter whose `expiration` has passed used to `continue` to the next filter. It now `break`s out of the loop.
- So an expired snooze filter now stops all later filters on that signal from being checked.
- **Snooze window today:** the filter's absolute `expiration` timestamp, compared in UTC. A snooze with no expiration is skipped with a warning. There is no duration unit.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
- **Default window:** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. That is still 45 minutes, with no change in behavior.
- **Per-filter dedup window:** this is a behavior change despite the refactor label.
  - Before, the code used `timedelta(minutes=f.window)`.
  - Now it uses `_window_start(f.window)`, which treats `f.window` as seconds.
  - A filter with `window=600` used to look back 600 minutes (10 hours) and now looks back 600 seconds (10 minutes).
  - The `SignalFilter.window` model column is documented as seconds and defaults to 3600 (1 hour). The Pydantic default is 600 (10 minutes).
  - The UI dialog `SignalFilterCreateDialog.vue` still labels the field "Window (minutes)" and offers 5, 10, 15, 20 and 30.
  - Filters created through that UI will therefore get windows of 5 to 30 seconds, not minutes.
  - I haven't checked whether other code converts the value between the UI and the database.

A fifth place involves a time value, but it isn't a snooze or dedup decision. In `signal/flows.py`, a deduplicated instance only triggers a case-thread update if at least 5 seconds have passed since the last cached update for that case.

I checked the commits that touched the signal service, flows, config and models. I also ran a content search for snooze, dedup, window and expiration across `src/dispatch`. Nothing else in the date range changed this decision logic.

----- next turn -----

Commit `917a0b7b` ("share the lookback window computation", 2025-08-14) broke it. The fix is in and the signal service tests pass.

**Cause:** `SignalFilter.window` holds minutes. The UI field is labelled "Window (minutes)", and the old code used `timedelta(minutes=f.window)`. The refactor added `_window_start(seconds)` and passed `f.window` straight in, with a comment saying the value is stored in seconds. A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases. No data is wrong, so existing filters work unchanged.

**Fix:** `filter_dedup` in `src/dispatch/signal/service.py` now calls `_window_start(f.window * 60)`, and the comment says minutes.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a window of 30 and an instance with a case from 10 minutes earlier. The new instance must be deduplicated into that case. It fails without the fix and passes with it.

Other things I noticed and left alone:
- The comment on `SignalFilter.window` in `signal/models.py` still says "seconds", and its default of `60 * 60` is wrong if the column is in minutes. The pydantic default of 600 has the same problem.
- Commit `086dc910` changed `continue` to `break` for an expired snooze filter in `filter_snooze`. An expired snooze now stops the check for any later snooze filters, which looks like a separate bug.
- The `filter_signal` docstring still says the default window is 1 hour. Commit `7a9fe810` made it configurable with a default of 45 minutes.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES