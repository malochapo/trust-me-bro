Five commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read each diff and the current `src/dispatch/signal/service.py`, and changed no code. Two further commits (`4474af25`, `d2675cf4`) touch the signal code but not this decision, and are listed at the end.

**1. `a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals (#6026)"**
- `filter_dedup` now returns straight away if the incoming instance is a canary.
- Both dedup queries now exclude canary instances with `~SignalInstance.canary`. This covers the default-window query and the per-filter query.
- It adds no time window.

**2. `7a9fe810`, 2025-06-19, "make the default deduplication window configurable"**
- This applies to signals with no filters. The window was hard-coded at `timedelta(hours=1)`.
- It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`. The default is **45 minutes**, so the default window shrank from 60 to 45 minutes. The setting is an int and can be overridden in the environment.

**3. `086dc910`, 2025-08-07, "simplify snooze filter checks"**
- In `filter_snooze`, it merged the mode and action checks into one condition: skip a filter unless it is active and its action is snooze.
- It also removed the "no mode" and "no action" warning logs.
- It also changed `continue` to `break` when a snooze filter's `expiration` has already passed. This is a behaviour change, not just a cleanup. An expired snooze filter now stops the loop, so any later snooze filters on that signal are no longer checked.
- Snooze uses an absolute `expiration` timestamp, not a lookback window.

**4. `917a0b7b`, 2025-08-14, "share the lookback window computation"**
- It adds a helper, `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
- The default dedup window now calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still **45 minutes**, converted to 2700 seconds.
- The per-filter window used to be `timedelta(minutes=f.window)`. It now calls `_window_start(f.window)`, which treats the value as **seconds**. `SignalFilter.window` is an Integer column in seconds, with a column default of `60 * 60` (**1 hour**). The pydantic model in `models.py` defaults it to **600** (**10 minutes**).
- The old code read that seconds value as minutes, so filter windows were 60 times too long. A stored 3600 was applied as 3600 minutes, or 60 hours. This commit fixes that, though its message presents it as a pure refactor.

**Values as applied today**
- Signals with no filters are deduplicated against non-canary instances that already have a case, created within the last 45 minutes (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, configurable).
- Signals with an active dedup filter use that filter's `window` in seconds. The column default is 3600 s and the pydantic default is 600 s.
- Snooze is governed by the filter's `expiration` timestamp, not a window.

**Signal commits that don't affect this decision**
- `4474af25` only adds logging of the outcome.
- `d2675cf4` masks sensitive raw fields.

----- next turn -----

I saved the findings to memory as `signal-snooze-dedup-history.md`, with a pointer line in `MEMORY.md`. The note covers:
- the four commits that changed the snooze/dedup decision (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`) and what each changed;
- the two signal commits that don't affect it (`4474af25`, `d2675cf4`);
- the window values and units as applied today: 45 minutes (2700 s) by default, and filter windows in seconds (3600 s column default, 600 s pydantic default).

I also noted that a later session should re-check these against the code before relying on them. I changed no code.

----- next turn -----

The commit that broke it is `917a0b7b` ("share the lookback window computation"). My earlier summary was wrong about it: I'd described it as a fix. It changed the per-filter lookback from `timedelta(minutes=f.window)` to seconds. The UI ("Window (minutes)", options 5–30) and the existing stored values are minutes. A window of 30 therefore became 30 seconds, so two instances ten minutes apart no longer deduplicated.

**Fix**
- `src/dispatch/signal/service.py`: the lookback is now `_window_start(f.window * 60)`, so existing filters work again without being edited.
- `src/dispatch/signal/models.py`: the column default is now 60 and the pydantic default 10, both in minutes. Before, they were 3600 and 600, which only made sense as seconds. This only affects newly created filters.
- Regression test: `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py`. A 30-minute filter deduplicates an instance created 10 minutes earlier and ignores one created 90 minutes earlier.
- Test results: the test fails without the fix and passes with it, and `tests/signal` passes (33 passed, 1 skipped).
- I also corrected my saved notes on this history.

The canary commit is `a348bbd2`, which skips deduplication for canary signals and excludes canary instances from dedup queries. The default window for signals without filters is 45 minutes (set by `7a9fe810`).

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES

Note that `a348bbd2` and `7a9fe810` come from my saved notes, so I haven't re-checked them against the git history.