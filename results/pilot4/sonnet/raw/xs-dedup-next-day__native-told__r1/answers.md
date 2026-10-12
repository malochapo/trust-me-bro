Six commits since 2025-05-22 touch the snooze or dedup logic in `src/dispatch/signal/service.py`. Four of them change how a signal instance is judged, and two of those are labelled "refactor" but change behavior. I didn't change any code.

**Decision-changing commits**

1. **`a348bbd2`** (2025-05-29, "fix(signal): don't dedup on canary signals", #6026)
   - `filter_dedup` now returns right away if the incoming instance is a canary.
   - Canary instances are also excluded as dedup matches, in both the no-filter default path and the per-filter path.
   - It adds no window and changes no window value.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable")
   - This applies to signals that have no filters at all.
   - The default window was a hard-coded `timedelta(hours=1)`. It now comes from the new setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, read from the environment and cast to `int`.
   - The default is **45 minutes**, so the commit also lowered the default from 60 to 45 minutes.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks")
   - It is labelled a refactor, but one line changes behavior.
   - The separate "no mode" and "no action" warnings were folded into one condition. That part is equivalent: a filter is skipped unless it is active and its action is snooze.
   - An expired snooze filter (`expiration <= now`) used to `continue` to the next filter. It now does `break`, so the loop stops and any later filters in the list are no longer checked.
   - The snooze time limit is each filter's `expiration` timestamp, compared in UTC. It is not a duration.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation")
   - It adds the helper `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - This is also labelled a refactor, but it changes a unit. The per-filter dedup window used `timedelta(minutes=f.window)` and now uses `_window_start(f.window)`, which means seconds.
   - The `SignalFilter.window` column is documented as seconds, with a default of 3600. Before this commit the code treated the stored value as minutes, so the effective lookback was 60 times longer than the column says.
   - The default path now calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes.

**Windows as the code applies them today**

| Case | Value | Unit |
|---|---|---|
| Signal with no filters (default dedup) | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 | minutes, converted to 2700 s |
| Signal with a dedup filter | `SignalFilter.window`, column default 3600 (1 hour) | seconds |
| Snooze | `SignalFilter.expiration` | absolute UTC timestamp |

The `window: int | None = 600` default in the Pydantic model at `models.py:282` is also in seconds, so it is 10 minutes. It differs from the 3600 column default.

**Other commits that touched the signal code but not these decisions**

- `4474af25` logs the outcome of each processed signal instance.
- `d2675cf4` masks sensitive raw fields before processing.
- `5e136d7b` adds entity and trigger views to the signal instance page.

I took the "decides snooze or dedup" scope from `filter_snooze` and `filter_dedup`, and didn't read the diffs of those three commits.

----- next turn -----

The commit that broke it is `917a0b7b` ("refactor(signal): share the lookback window computation"). It's fixed, and the new regression test fails on the old code and passes on the fix.

**Cause:** that refactor added `_window_start(seconds)`. It passed `f.window` to it as seconds. `SignalFilter.window` is stored in minutes. The UI dialog is labelled "Window (minutes)" and offers 5/10/15/20/30. A filter set to 30 therefore looked back only 30 seconds, so the 10-minute-old instance never matched and a second case was opened. The refactor also changed the default-window path to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is equivalent. The wrong `# stored in seconds` comment came from the same commit.

**Fix (`src/dispatch/signal/service.py`):**
- `_window_start` now takes minutes.
- Existing filters work unedited, because their stored values were always minutes.
- I corrected the stale comment and the `filter_signal` docstring, which said "1-hour" for the default.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a filter with `window=30` and an instance 10 minutes old, and expects the new instance to be deduplicated into the same case. The whole `tests/signal` suite passes (33 passed, 1 skipped).

**Left alone:** the `SignalFilter.window` model default (`60 * 60`, commented as seconds) and the schema default (`600`) still read as seconds. If that were corrected to minutes it would change what new filters default to, so I didn't touch it. Say if you want it changed.

I haven't saved anything to memory and haven't committed.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES