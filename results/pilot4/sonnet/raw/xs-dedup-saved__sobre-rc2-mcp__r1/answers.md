Five commits since 2025-05-22 touched the snooze/dedup decision in `src/dispatch/signal/service.py`, and `config.py` for the window setting. Two of them changed behavior in ways their messages don't say. I read the diffs and the current code but ran nothing.

**`a348bbd2` (2025-05-29), "don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early when the new instance is a canary.
- Both dedup queries (the default one and the per-filter one) now exclude earlier canary instances with `~SignalInstance.canary`. A canary can no longer be a match target.
- This commit changed no window values. At the time the default window was still a hard-coded 1 hour.

**`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default window, used when a signal has no filters, went from a hard-coded `timedelta(hours=1)` to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
- That setting is an int read from the environment, **in minutes, default 45**. So the default quietly dropped from 60 to 45 minutes.

**`086dc910` (2025-08-07), "simplify snooze filter checks"**
- It collapsed the separate mode and action checks (and their "no mode" / "no action" warnings) into one condition: skip unless the filter is `active` and its action is `snooze`.
- It also changed what happens when a snooze filter has expired (`expiration <= now`, compared in UTC). The code used to `continue` to the next filter and now does `break`. An expired snooze therefore stops the loop, and any later non-expired snooze filter on that signal is no longer evaluated. I'd treat that as a possible regression.
- Snooze has no lookback window. It depends only on the filter's `expiration` timestamp, and a filter with no expiration is skipped with a warning.

**`917a0b7b` (2025-08-14), "share the lookback window computation"**
- It added `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
- The default window is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, which is still 45 minutes.
- For filter-based dedup, the old code was `timedelta(minutes=f.window)` and the new code treats `f.window` as **seconds**. The model column `SignalFilter.window` defaults to 3600 and its comment says seconds, so the old code was effectively applying the value as minutes. A stored `3600` was a 60-hour lookback and is now 1 hour. The pydantic schema default `window: int | None = 600` now means 10 minutes. Any existing filter whose `window` was set expecting minutes now gets a much shorter window.

**Current behavior**
1. Snooze is checked first.
2. Dedup runs only if the instance wasn't snoozed.
3. A signal with no filters is deduplicated against the most recent non-canary instance that already has a case, within 45 minutes by default.
4. A signal with filters uses each active deduplicate filter's `window` in seconds. The earliest match inside that window supplies the case.

The docstring on the function at `service.py:873` still says "1-hour window", which no longer matches the 45-minute default.

I left out `4474af25`, which only adds logging in `flows.py`.

----- next turn -----

I saved the findings to memory as `signal-snooze-dedup-history.md` and added a line for it to `MEMORY.md`. The note has the four commits with their hashes and window changes, how snooze and dedup work now, and the stale "1-hour" docstring. It also records two open items for a later session: whether the `break` in the expired-snooze handling is a regression, and the docstring fix. No code was changed.

----- next turn -----

The culprit is `917a0b7b` (2025-08-14, "share the lookback window computation"). It added `_window_start(seconds)` and switched the per-filter dedup from `timedelta(minutes=f.window)` to seconds. The UI value, and every filter already stored, is in minutes. A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, so a filter's `window` means minutes again. The default-window call no longer multiplies by 60. Stored filters work as they are, with no data migration.
- `src/dispatch/signal/models.py`: I changed the unit comment and the defaults to match minutes: the model default is 60 and the schema default is 10. Before, they were 3600 and 600 and only made sense as seconds. This only affects newly created filters.

**Test**
- I added `test_filter_actions_deduplicate_window_is_in_minutes`. It sets a filter with window 30 and a case-bearing instance 10 minutes old, then checks the new instance is deduplicated onto that case.
- It fails without the fix and passes with it. `tests/signal` shows 33 passed, 1 skipped.

**Corrections to yesterday's list**
- The default window: `7a9fe810` made it configurable and dropped it from 60 to 45 minutes. That was a deliberate change, so I left it.
- I didn't touch the `continue` to `break` change in `086dc910`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES