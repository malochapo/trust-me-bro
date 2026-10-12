Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. Three of them (`a348bbd2`, `7a9fe810`, `917a0b7b`) changed the dedup rules or window, and the fourth (`086dc910`) changed the snooze checks. All of this lives in `src/dispatch/signal/service.py`, in `filter_signal`, `filter_snooze` and `filter_dedup`. I changed no code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals (#6026)".
   - `filter_dedup` now returns early, with no dedup, when the incoming instance is a canary.
   - Canary instances are also excluded from the candidates it matches against, in both the default query and the per-filter query.
   - It changed no time window. At this point the default window was still hard-coded to 1 hour.

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable".
   - The default window, used when a signal has no filters at all, was `timedelta(hours=1)`.
   - It now comes from the new setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, which defaults to **45 minutes**.
   - So the default window shrank from 60 to 45 minutes, and it can be set through that environment variable.

3. **`086dc910`** (2025-08-07), "simplify snooze filter checks".
   - It removed the "no mode" and "no action" warning branches.
   - It merged the active-mode and snooze-action checks into one condition.
   - It also changed what happens to an expired snooze filter. The code used `continue`, so it moved on to the next filter. It now uses `break`, so it stops checking filters at the first expired snooze and later snooze filters are not evaluated.
   - Despite the "refactor" label, that last point changes behaviour.
   - Snooze has no lookback window. It depends only on the filter's `expiration` timestamp, compared against the current UTC time, and on the filter's expression, if it has one.

4. **`917a0b7b`** (2025-08-14), "share the lookback window computation".
   - It added the helper `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - The default window is now computed as `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes and unchanged in effect.
   - For per-filter dedup, the code used `timedelta(minutes=f.window)`. It now uses `_window_start(f.window)`, so `f.window` is treated as seconds.
   - Despite the "refactor" label, this changes behaviour. The column comment in `models.py` says `SignalFilter.window` is in seconds, so the old code was applying minutes to a seconds value. The model default is 3600, which would have meant 3600 minutes (60 hours) under the old code. It now means 1 hour.
   - The pydantic input default is `window = 600`. Under the new code that is 10 minutes, where the old code would have applied 600 minutes.

**Values as applied today**

| Case | Window |
|---|---|
| Signal with no filters | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` = 45 minutes by default (converted to 2700 seconds), matched against the most recent non-canary instance that already has a case |
| Signal with dedup filters | `SignalFilter.window`, in seconds (model default 3600 = 1 hour; API/pydantic default 600 = 10 minutes) |
| Snooze | No window, only the filter's expiration time |

**A stale docstring.** The `filter_signal` docstring still says the default dedup groups instances "for a 1-hour window". That is out of date, since the default is 45 minutes.

**Not a decision rule.** `flows.py` has a separate 5-second throttle (`timedelta(seconds=5)`) on updating the Slack thread for deduplicated signals. It doesn't affect whether an instance is snoozed or deduplicated, so I left it out. I also checked the other commits that touched the signal files, such as `4474af25` (logging) and `d2675cf4` (redaction). They don't change the snooze or dedup logic.

----- next turn -----

I saved the task and two findings to the sobre session. A new session can bring them back with `sobre_session` and `action="load"`.

- **Task:** which commits since 2025-05-22 changed how a signal instance is snoozed or deduplicated, including the time windows. It was read-only, with no code changed.
- **Finding 1:** the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`), what each changed, and the window values as applied today. The same finding notes that `086dc910` and `917a0b7b`, though labelled refactors, changed behaviour. It also lists the commits and code I ruled out.
- **Finding 2:** the `filter_signal` docstring in `service.py` still says the default dedup window is 1 hour, but the default has been 45 minutes since `7a9fe810`. I left it unfixed.

I didn't add a separate memory file. The findings are about this repository's git history, which a new session can recover from the repo, so the session record is enough.

----- next turn -----

The commit that broke deduplication windows is `917a0b7b` (2025-08-14, "share the lookback window computation"). I fixed it, added two regression tests, and all of `tests/signal` passes (34 passed, 1 skipped).

**Cause.** That commit added `_window_start(seconds)` and changed the filter path from `timedelta(minutes=f.window)` to `_window_start(f.window)`. It also added a comment, "SignalFilter.window is stored in seconds", which is wrong. The UI offers "Window (minutes)" with 5, 10, 15, 20 and 30, so stored values are minutes. After the commit, a window of 30 was treated as 30 seconds, so two instances ten minutes apart never grouped. The model's column comment already said "seconds", but the stored data and the UI both use minutes.

**Fix.**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter path passes `f.window` unchanged, so existing filters work without edits. The default no-filter path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, with no `* 60`.
- `src/dispatch/signal/models.py`: the column's Python-side default is now 60 with a "minutes" comment. It was 3600, which would have meant 60 hours once read as minutes. This only affects new filters created without an explicit window.

**Tests** (in `tests/signal/test_signal_service.py`):
- `test_filter_actions_deduplicate_window_is_in_minutes`: with window=30, an instance 10 minutes old is deduplicated. With the fix stashed, this one fails.
- `test_filter_actions_deduplicate_outside_window`: with window=30, an instance 40 minutes old is not deduplicated. It passes with or without the fix, so it only guards against the window being too wide.

I had no record of yesterday's list, so I re-derived the commits from `git log` since 2025-05-22.

**The other two answers:**
- **Canary:** `a348bbd2` (2025-05-29, "don't dedup on canary signals").
- **Default window:** signals without a filter group for 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It became configurable in `7a9fe810`.
- **Stale docstring:** the `filter_signal` docstring still says "1-hour window". I didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES