Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`. I haven't changed any code.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals (#6026)"**
- `filter_dedup` now returns immediately if the incoming instance is a canary, so canaries are never deduplicated.
- Both dedup queries (the default one and the per-filter one) also exclude existing canary instances with `~SignalInstance.canary`. A canary can't become the instance that a new signal is deduplicated against.
- This commit changed no window value. The default window was still a hard-coded `timedelta(hours=1)`.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- This applies to signals with no filters. The hard-coded 1-hour window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read from the environment in `config.py`.
- The value is an integer in **minutes**, and the default is **45**. So the default dropped from 60 to 45 minutes.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- `filter_snooze` was condensed to a single check: skip any filter whose mode isn't `active` or whose action isn't `snooze`.
- The old per-field warning logs for a missing mode or action are gone. Missing values are now skipped silently.
- Behaviour change: when a filter's `expiration` has passed, the loop now does `break` instead of `continue`. An expired snooze filter now stops the scan, so any later filters in the list are not checked. If the filter order isn't by expiration, a later, still-valid snooze filter would be skipped. This looks like an unintended side effect of the refactor.
- The expiration comparison is unchanged: `expiration` is treated as UTC and compared with now.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds a helper, `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
- The default window now calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes, so behaviour is unchanged.
- Per-filter windows now call `_window_start(f.window)`, treating `f.window` as **seconds**. Before this commit the code used `timedelta(minutes=f.window)`.
- This is a real behaviour change. `SignalFilter.window` is defined as seconds, with a default of `60 * 60` (1 hour), and the Pydantic schema default is `600` (10 minutes). The old code read those numbers as minutes, which made the effective window 60 times too long. The new code matches the model's definition.
- A filter stored as `3600` is now a 1-hour window. Before it was about 60 hours. Any existing filters tuned around the old behaviour will now match over much shorter periods.

**Windows as applied today**

| Case | Window |
|---|---|
| Signal with no filters (default dedup) | 45 minutes, configurable via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` |
| Signal with a dedup filter | `SignalFilter.window` in seconds (model default 3600 s, schema default 600 s) |
| Snooze | No lookback window. It is governed by the filter's `expiration` timestamp (UTC). |

The docstring around line 873 in `service.py` still says "1-hour window". It is stale, since the default is now 45 minutes.

Dedup only runs if the instance wasn't snoozed (`service.py:887`).

----- next turn -----

I saved the findings to memory in `signal-snooze-dedup-commits.md` and added a line for it to `MEMORY.md`. The note covers:
- the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`) and what each changed;
- the window values and units as the code applies them today;
- the two open issues: the `break` regression in `filter_snooze` and the stale "1-hour" docstring.

I didn't change any code.

----- next turn -----

The cause was commit `917a0b7b`, and I've fixed it and added a regression test. In `tests/signal/test_signal_service.py` the new test passes with the fix and fails without it, and the rest of that file passes (15 passed, 1 skipped).

**Cause:** `917a0b7b` ("share the lookback window computation") changed how a filter's `window` is read. It used to be `timedelta(minutes=f.window)`. After the refactor it went through `_window_start(f.window)`, which treats the number as seconds. A window of 30 therefore became 30 seconds, and the two instances ten minutes apart opened two cases.

**Fix:**
- **Window unit:** in `src/dispatch/signal/service.py`, filter windows are minutes again (`_window_start(f.window * 60)`). Stored filters are unchanged, so existing ones work without edits.
- **Regression test:** `test_filter_dedup_window_is_in_minutes` puts two instances for the same entity ten minutes apart under a filter with window 30 and checks the second is deduplicated.
- **Comments:** I corrected the comment on `SignalFilter.window` in `models.py`, which said seconds. I also updated the stale "1-hour window" docstring in `filter_dedup`.

**Left as is:** the column default (3600) and the pydantic default (600) are both read as minutes now, so they are much longer than their comments implied. Changing them would need a migration, so I didn't touch them.

**Left as is:** the expired-snooze `break` from `086dc910`, which skips later filters, is still there. I noted it earlier as likely unintended but didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES