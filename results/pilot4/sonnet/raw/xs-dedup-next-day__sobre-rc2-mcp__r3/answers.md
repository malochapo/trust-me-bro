Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs and the current `src/dispatch/signal/service.py`. I did not run anything or change any code.

**`a348bbd2` (2025-05-29), "don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early, with no dedup, when the incoming instance is a canary.
- Canary instances are also excluded from the lookback queries, with `~SignalInstance.canary`, in both the default path and the per-filter path.
- It changed no window values.

**`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default window for signals with no filters was a hard-coded `timedelta(hours=1)`.
- It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`, an int that defaults to **45 minutes**.
- The 1-hour wording remains in the `filter_signal` docstring. It is stale.

**`086dc910` (2025-08-07), "simplify snooze filter checks"**
- Its message calls it a refactor, but it changes behaviour in `filter_snooze`.
- The separate checks for a missing mode and a missing action are folded into one condition: `mode != active or action != snooze` → `continue`. The "no mode" and "no action" warnings are gone.
- An expired snooze filter (`expiration <= now`, UTC) used to `continue` to the next filter. It now does `break`, so any filters after an expired snooze are no longer checked. A later, still-active snooze filter on the same signal will not apply.
- A filter with no expiration still logs a warning and is skipped.
- Snooze has no lookback window. It is bounded only by the filter's `expiration`.

**`917a0b7b` (2025-08-14), "share the lookback window computation"**
- Its message calls it a refactor, but it changes behaviour for filter windows.
- It adds `_window_start(seconds)`, which returns `now(UTC) - timedelta(seconds=seconds)`.
- **Default window:** it now calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes, now converted to 2700 seconds, so nothing changes here.
- **Per-filter window (`SignalFilter.window`):** this was `timedelta(minutes=f.window)` and is now `timedelta(seconds=f.window)`. The column is documented as seconds, with a default of `60 * 60` = 3600 s (1 hour). The Pydantic schema default is `600`, which is 10 minutes under the seconds reading. Before this commit, a stored value of 3600 was treated as 3600 minutes, which is 60 hours. It is now 1 hour. Existing filters therefore dedup over a much shorter lookback than before.

**Current behaviour** (`filter_signal`)
1. Run `filter_snooze`.
2. If the instance is not snoozed, run `filter_dedup`.
3. Otherwise the instance's `filter_action` is set to `none`.

In `filter_dedup`:
- Canary instances are skipped.
- A signal with no filters uses the 45-minute default window, which is configurable. It matches the latest non-canary instance of the same signal that has a case, whatever its entities.
- Otherwise each active dedup filter uses its own window in seconds, and matches on entities, taking the earliest matching instance.

I also looked at `4474af25` (logging the outcome of each processed instance), `d2675cf4` and `5e136d7b`. None of them changes the snooze or dedup decision logic.

----- next turn -----

The commit that broke it is 917a0b7b ("refactor(signal): share the lookback window computation"). It's fixed, and the signal tests pass (33 passed, 1 skipped).

**Cause.** The deduplication filter used to compute its lookback with `timedelta(minutes=f.window)`. The UI offers 5, 10, 15, 20 and 30 and stores them as minutes. 917a0b7b replaced that with a shared `_window_start(seconds)` helper and added a comment saying `SignalFilter.window` is stored in seconds. That comment was wrong, so a window of 30 became 30 seconds. Instances ten minutes apart no longer matched and each opened its own case. The same commit also changed the default-window path to `* 60` so it stayed in minutes.

**Fix.**
- `_window_start` in `src/dispatch/signal/service.py` now takes minutes, and the default-window call no longer multiplies by 60.
- The wrong comments in `service.py` and in the `window` column comment in `src/dispatch/signal/models.py` are corrected.
- No data migration is needed, because the stored values were always minutes.

**Regression test.** `test_filter_actions_deduplicate_window_is_in_minutes` uses a filter with window 30 and an earlier instance 10 minutes old. It fails without the fix and passes with it. The existing dedup tests didn't catch this: in the one I inspected, the filter never attached to the signal, so the default-window branch ran instead.

**Left alone.** The `window` column default is `60 * 60` and the pydantic default is 600. Read as minutes, those are 60 hours and 10 hours. They only affect filters created without an explicit window; I didn't change them.

The other commits you listed are not the cause. The default-window setting (7a9fe810) and the canary-signal handling (a348bbd2) don't touch filter windows. 086dc910 changes the snooze checks.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES