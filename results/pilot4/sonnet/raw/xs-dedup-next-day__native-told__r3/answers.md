Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`, and `7a9fe810` also touches `src/dispatch/config.py`. I only read the code and history; nothing was changed.

1. **`a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
   - `filter_dedup` now returns early for canary instances.
   - Canary instances are also excluded from the candidate set in both dedup paths, the default one and the per-filter one.
   - It added no window and changed none. At the time the default window was a hard-coded 1 hour.

2. **`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
   - This applies to signals that have no filters. The hard-coded `timedelta(hours=1)` became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
   - The setting is in `config.py`. It is cast to an int and defaults to **45 minutes**, not the old 60.
   - Deployments that don't set it will therefore dedup over a shorter window than before.

3. **`086dc910` (2025-08-07), "simplify snooze filter checks"**
   - It is labelled a refactor, but it changed behaviour in `filter_snooze`.
   - It dropped the separate "no mode" and "no action" warning-and-skip checks. These are now one condition: skip unless the filter is `active` and its action is `snooze`.
   - An expired snooze filter used to `continue` to the next filter. It now `break`s out of the loop, so any later snooze filters are no longer checked.
   - A filter with no expiration is still skipped with a warning. Snooze has no window of its own. It uses the filter's expiration timestamp, compared in UTC.

4. **`917a0b7b` (2025-08-14), "share the lookback window computation"**
   - This also reads as a refactor, but it changed a unit. It added the helper `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - **Default dedup window:** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` is passed in, so it is still 45 minutes, the default.
   - **Per-filter dedup window:** the old code was `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats `f.window` as **seconds**.
   - The `SignalFilter.window` column is documented as seconds, with a default of `60*60`, which is 1 hour. The Pydantic schema default is 600, which is 10 minutes.
   - Before this commit the code read that value as minutes. Any filter whose window was stored as seconds had been looked back over 60 times too long, and the commit corrects that.

Windows as applied today:

| Case | Window |
|---|---|
| Signal with no filters | 45 minutes by default, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. |
| Signal with a dedup filter | `SignalFilter.window` in seconds. The column default is 3600 s (1 hour), and the schema default is 600 s (10 minutes). |
| Snooze filter | No lookback window. It is active until the filter's `expiration`. |

Snooze is checked first. Dedup only runs if the instance wasn't snoozed.

----- next turn -----

The test now fails without the fix and passes with it.

Deduplication windows broke in **917a0b7b** ("share the lookback window computation", 2025-08-14). It changed the filter lookback from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. It did this on the wrong assumption that `window` is stored in seconds. The UI offers the window in minutes (5 to 30), and existing rows hold minutes. A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases.

The other commits you listed are not the cause:
- 7a9fe810 made the default window configurable.
- 086dc910 simplified the snooze checks.
- a348bbd2 made canary signals skip deduplication.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. Filters use `f.window` as minutes, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly. Existing filters work without edits. I also corrected the `filter_signal` docstring, which still said "1-hour window".
- `src/dispatch/signal/models.py`: the column default and comment said 3600 seconds, which would now read as 3600 minutes. I changed the default to 60 minutes for new filters.

**Test**
`test_filter_actions_deduplicate_window_is_in_minutes` uses a 30-minute filter and an earlier instance 10 minutes old that has a case. It asserts the new instance is deduplicated into that case. It fails on the old code and passes now; the rest of `tests/signal/test_signal_service.py` passes too (15 passed, 1 skipped).

The existing deduplication tests append filters to `signal.filters` without adding them to the session first. In my first attempt the filter never attached, so the test used the default 45-minute path and passed on the old code too. I added `session.add(signal_filter)` in the new test. I did not touch the other tests, so they may still be exercising the default path instead of their filters.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES