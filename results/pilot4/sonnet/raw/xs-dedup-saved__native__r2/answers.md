Five commits since 2025-05-22 touched the snooze/dedup decision in `src/dispatch/signal/service.py` and `src/dispatch/signal/flows.py`. Four of them changed behavior or the code's structure. The fifth only added logging. I haven't changed any code.

**Commits**

1. `a348bbd2` (2025-05-29, #6026), *don't dedup on canary signals*
   - `filter_dedup` now returns early when the incoming instance is a canary, so canaries are never deduplicated.
   - Both dedup queries, the default one and the per-filter one, now exclude earlier canary instances (`~SignalInstance.canary`). A canary can't become the case that a later instance dedups into.
   - It did not change any window.

2. `4474af25` (2025-06-10), *log the outcome of each processed signal instance*
   - It only adds `log.info` calls in `signal_instance_create_flow`, one for filtered instances and one for case creation.
   - It does not change the decision logic.

3. `7a9fe810` (2025-06-19), *make the default deduplication window configurable*
   - The window used for signals that have no filters was hard-coded as `timedelta(hours=1)`.
   - It is now read from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`. That setting is an int in minutes and defaults to 45.
   - This silently shortened the default from 60 to 45 minutes. The commit message doesn't mention that.

4. `086dc910` (2025-08-07), *simplify snooze filter checks* (labelled a refactor)
   - It collapsed the separate mode and action checks in `filter_snooze` into one condition.
   - It dropped the "has no mode" and "has no action" warnings. A filter with no mode or action is still skipped, now silently.
   - It also changed an expired snooze filter from `continue` to `break`. Once one active snooze filter has expired, the loop stops, so any later snooze filters on that signal are never checked. Before, they were still evaluated, so this is a behavior change.

5. `917a0b7b` (2025-08-14), *share the lookback window computation* (labelled a refactor)
   - It added `_window_start(seconds)`, which returns `now(UTC) - timedelta(seconds=seconds)`.
   - Default window: the call is `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, so the result is unchanged at 45 minutes (2700 s).
   - Per-filter window: it was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as seconds. This is a real unit change.
   - The column is documented as seconds and defaults to `60 * 60`, which is 1 hour. The pydantic model default is 600, which is 10 minutes.
   - Before this commit, a stored value of 3600 was applied as 3600 minutes, or 60 hours. Now it is applied as 1 hour. The fix makes the code match the column's documented unit, but it shrinks the effective window on existing filters by a factor of 60.

**Windows as the code applies them today**

| Case | Value | Unit | Effective |
|---|---|---|---|
| Signal with no filters (default dedup) | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 | minutes, converted ×60 to seconds | 45 min |
| Signal with an active dedup filter | `SignalFilter.window`, column default 3600, pydantic default 600 | seconds | 1 h by column default, 10 min by pydantic default |
| Snooze | No lookback window. It uses the filter's `expiration` timestamp, compared to now in UTC. | n/a | n/a |

**Stale or inconsistent leftovers**
- The `filter_signal` docstring still says the default is a "1-hour window", which is no longer true.
- The UI filter dialog offers window choices `[5, 10, 15, 20, 30]` in `SignalFilterCreateDialog.vue`. They look like minutes, but the backend now reads them as seconds. A user who picks 30 would get a 30-second window. I didn't check how the dialog converts the value on save.

----- next turn -----

I saved the findings to memory as `signal-snooze-dedup-history.md` and added a pointer to it in `MEMORY.md`. The note has:
- the five commits with their hashes and what each changed;
- the window values as the code applies them today;
- the two leftovers: the stale "1-hour" docstring, and the UI window choices that look like minutes while the backend reads seconds.

I made no code changes. A new session can pick up from there, for example by checking how the UI converts the window value on save.

----- next turn -----

**Culprit:** `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). It changed the per-filter window from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI and the stored data are in minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart no longer matched, which is why they opened two cases.

**Fix:**
- In `src/dispatch/signal/service.py`, `filter_dedup` now uses `_window_start(f.window * 60)`. Windows are minutes again, so existing filters work without edits and no migration is needed.
- I corrected the `filter_signal` docstring, which still said "1-hour window". I also fixed the `SignalFilter.window` comment in `models.py`, which said seconds.
- I left the column default (3600) and the pydantic default (600) as they were. They look odd as minutes, but changing them would alter behavior for new filters you didn't ask me to touch.

**Test:** I added `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It has an instance from 10 minutes ago, a new one, and a filter with window=30, and it expects the new one to be deduplicated.
- The test fails without the fix and passes with it.
- `python -m pytest tests/signal` gives 33 passed and 1 skipped.

The canary change is `a348bbd2` (2025-05-29, #6026): canary signals skip dedup, and earlier canary instances are excluded from the dedup queries.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES