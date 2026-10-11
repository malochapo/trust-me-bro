Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup. The logic is in `src/dispatch/signal/service.py`: `filter_snooze`, `filter_dedup` and the `_window_start` helper. The snooze-then-dedup ordering itself is unchanged. I haven't changed any code.

**Commits that changed the decision**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026).
   - `filter_dedup` now returns early if the incoming instance is a canary.
   - Both dedup queries, the default one and the per-filter one, now exclude canary instances with `~SignalInstance.canary`.
   - This adds no new window.

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable".
   - The default window used when a signal has no filters was hard-coded as `timedelta(hours=1)`.
   - It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
   - The default of that setting is **45 minutes**, so the default window dropped from 60 to 45 minutes unless the env var is set.

3. **`086dc910`** (2025-08-07), "simplify snooze filter checks".
   - It removed the "no mode" and "no action" warnings and merged the mode and action checks into one condition.
   - It also changed what happens when an active snooze filter has expired. That case used to `continue` to the next filter; it now `break`s out of the loop.
   - So an expired snooze stops evaluation of any later snooze filters on that signal, which can change which instances get snoozed.
   - Snooze filters use an absolute `expiration` timestamp, compared in UTC, rather than a lookback window.
   - A filter with no expiration is still skipped with a warning.

4. **`917a0b7b`** (2025-08-14), "share the lookback window computation".
   - It added `_window_start(seconds)`, which returns now minus that many seconds.
   - The default window is now computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, so it is still 45 minutes.
   - The per-filter window changed units. It was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats `f.window` as **seconds**. This matches the `SignalFilter.window` column, which is documented as seconds with a default of `60 * 60`, i.e. 3600 s (1 hour).
   - A stored value of 600 used to mean 600 minutes and now means 10 minutes, so existing filters with large values get much shorter windows.

**Windows as applied today**

| Window | Value and unit | Applies to |
|---|---|---|
| Default dedup, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | 45 minutes (converted to 2700 s) | Signals with no filters |
| Per-filter dedup, `SignalFilter.window` | seconds; DB column default 3600 (1 hour), Pydantic schema default 600 (10 minutes) | Active filters with a deduplicate action |
| Snooze | no lookback; active until `expiration` (UTC timestamp) | Active snooze filters |

- **Stale docstring:** the docstring on the function that runs the snooze and dedup filters still says the default is "1-hour window". That predates `7a9fe810` and no longer matches the code.
- **Excluded commit:** `4474af25` (2025-06-10) only adds logging of each instance's outcome in `flows.py`, so I left it out.

----- next turn -----

**Cause:** `917a0b7b` ("share the lookback window computation", 2025-08-14). Before it, a filter's window was applied as `timedelta(minutes=f.window)`. That commit started treating the stored value as seconds, because the column comment said seconds. The UI field is labelled "Window (minutes)" and stores 5, 10, 15, 20 or 30, so a window of 30 became 30 seconds. Your two instances ten minutes apart fell outside it and opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: the filter window is applied as minutes again (`_window_start(f.window * 60)`). Existing filters need no edits or migration.
- `src/dispatch/signal/models.py`: I corrected the column comment to minutes and changed the defaults to match. The Python column default goes from 3600 to 60, and the API schema default from 600 to 10. These defaults were written in seconds and would otherwise now read as 60 hours and 10 hours.
- The default 45-minute window for signals without filters (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) was already correct and is untouched.
- The default change only affects filters created through the API without a window.

**Test:** I added `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It creates an instance ten minutes old and a new one with a window of 30, and expects the new one to be deduplicated. It fails without the service fix. With the fix, all of `tests/signal` passes (33 passed, 1 skipped).

Filters created after 2025-08-14 may have been saved with seconds-sized values. I didn't check for any, and this fix would turn such a value into minutes.

----- next turn -----

**Cause:** `086dc910` ("simplify snooze filter checks", 2025-08-07), the same batch as before. In `filter_snooze`, an expired snooze filter used to `continue` to the next filter. That commit changed it to `break`. With an expired filter listed ahead of the valid one for the same user, the loop stopped at the expired one. The valid snooze was never evaluated, so new instances for that user were no longer snoozed.

**Fix:** in `src/dispatch/signal/service.py`, an expired filter now `continue`s again, so later filters still get checked.

**Test:** I added `test_filter_actions_snooze_expired_then_valid` in `tests/signal/test_signal_service.py`. It puts a filter that expired 7 days ago ahead of one valid for 30 days, both matching the same entity. It expects the instance to be snoozed. It fails without the fix. With the fix, all of `tests/signal` passes (34 passed, 1 skipped).

None of this is committed. The uncommitted changes also include the earlier dedup-window fix.

----- next turn -----

**Recap**

- **Dedup windows:** commit `917a0b7b` made the per-filter window count seconds instead of minutes. The UI stores minutes, so a window of 30 acted as 30 seconds. `filter_dedup` in `service.py` now multiplies the window by 60 again. The column and schema defaults were corrected to minutes (60 and 10). I added a regression test, which fails without the fix and passes with it.
- **Snoozing:** commit `086dc910` changed `continue` to `break` for expired snooze filters. An expired filter listed ahead of a valid one stopped the loop, so the valid snooze never applied. It is back to `continue`, with a regression test.
- **Canary signals:** commit `a348bbd2` made canary instances skip deduplication and excluded them from the dedup lookups. I did not change this.
- **Default window:** signals without any filter group instances for 45 minutes. Commit `7a9fe810` made this configurable, and `917a0b7b` only rewrote how it is computed.
- **Status:** the fixes and tests are uncommitted. All of `tests/signal` passes (34 passed, 1 skipped).

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES