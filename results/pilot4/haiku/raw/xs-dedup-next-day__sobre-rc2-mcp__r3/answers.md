Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or changed the windows it uses. No code was changed.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - Canary signal instances skip deduplication entirely. They are also excluded as match candidates in both the default path and the filter path.
   - Snooze is not affected.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - The default window for signals with no dedup filter was hard-coded to 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`).
   - Today it is **45 minutes (2700 s)**, unless the env var overrides it.
   - The docstring of `filter_signal` in `src/dispatch/signal/service.py` still says "1-hour window", so it is stale.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - The separate guards for a missing `mode` or `action`, which logged warnings, were folded into one condition.
   - Behavior change: when a snooze filter has expired, the loop now `break`s instead of `continue`ing. Snooze filters after it are no longer checked. Before, they were.
   - Snooze has no time window of its own. It is governed by the filter's `expiration` datetime.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Added `_window_start()` and used it for both windows.
   - Behavior change: the filter-dedup window was previously `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats the value as **seconds**. The commit message does not mention the unit change.
   - Current values:
     - Filter dedup window (`SignalFilter.window`): seconds. The API schema default is **600 s (10 min)** (`src/dispatch/signal/models.py:282`). The DB column default is **3600 s (1 h)** (`models.py:206`).
     - Default dedup window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` = **2700 s**.

**Concern to check:** Commit `917a0b7b` likely shrinks existing filter dedup windows by 60×. A stored `window` of 600 used to mean 10 hours and now means 10 minutes. The UI does not convert units (`src/dispatch/static/dispatch/src/signal/filter/store.js`). If the seconds interpretation was not intended, existing rows need a data fix or the code needs reverting. I did not check whether any migration or data change accompanied it.

I also checked `5e136d7b` (the signal instance page UI), `4474af25` (logging outcomes), and `d2675cf4` (masking raw fields). They don't change the snooze or dedup decision.

----- next turn -----

The window bug was introduced by `917a0b7b` ("refactor(signal): share the lookback window computation"). It changed the deduplication lookback from `timedelta(minutes=f.window)` to treating `f.window` as seconds. A 30-minute filter therefore looked back only 30 seconds, so two instances ten minutes apart opened two cases.

I don't have the earlier list from yesterday, so I rebuilt it from `git log --since=2025-05-22` and the code.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The filter window and the default window both go through it. Existing filter values are unchanged, so no filter needs editing. The stale comments that said "seconds" and "1-hour" now match the code.
- `src/dispatch/signal/models.py`: the column comment now says minutes, as the UI does.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes`. It creates an instance ten minutes old, then a new one under a 30-minute deduplicate filter, and expects deduplication. It fails when the seconds bug is reintroduced and passes with the fix.

`python -m pytest tests/signal` gives 33 passed, 1 skipped. I did not commit.

**Other findings, not changed**
- `086dc910` ("simplify snooze filter checks") changed `continue` to `break` for an expired snooze filter. Once one snooze filter has expired, the remaining snooze filters are skipped. This is a snooze bug, not a window bug, so I left it alone.
- The defaults are inconsistent with minutes. The schema default is `window: int = 600` (10 hours) and the column default is `60 * 60` (60 hours). I left them because changing them alters behaviour for filters created without a window.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES