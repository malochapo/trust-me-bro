Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. No code was changed.

**Commits**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*
   - Canary instances skip deduplication entirely: `filter_dedup` returns early when `signal_instance.canary` is set.
   - Canary instances are also excluded as match candidates in both dedup paths (the default path and the custom-filter path).
   - No window values changed.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - The default window for signals with no dedup filter was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), which is read in minutes and defaults to **45 minutes**.
   - The code converts that to seconds (`* 60`) before use.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - The mode/action checks in `filter_snooze` were merged into one condition. The per-check warnings for a missing mode or action were dropped, so those filters are now skipped silently.
   - Behaviour change: an expired snooze filter used to `continue` to the next filter, and now `break`s out of the loop. Any later active snooze filters on the same signal are no longer evaluated.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Extracted `_window_start(seconds)`. The default-window call now passes `minutes * 60`.
   - Behaviour change: custom dedup filters used to compute `timedelta(minutes=f.window)`. The new code calls `_window_start(f.window)` and the comment says `SignalFilter.window` is **seconds**. So a custom dedup window is now 60× shorter than before for existing filters, and the commit message does not mention this.

**Windows as the code applies them today** (`src/dispatch/signal/service.py`)

- **No dedup filter (default):** 45 minutes, configurable via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (minutes). Matches the newest instance of the same signal that already has a case.
- **Custom dedup filter:** `f.window` in **seconds**. The window is measured back from now on `created_at`.
- **Snooze:** no time window. It applies until `f.expiration`, which is checked against now.

**Defaults for `SignalFilter.window`** (`src/dispatch/signal/models.py`)

- The SQLAlchemy column defaults to `60 * 60` = 3600 seconds (line 206).
- The Pydantic model defaults to `600` (line 282). These disagree. I did not check which path creates filters in practice, so I can't say which default applies.

**Other things I noticed**

- The `filter_dedup` docstring still says the default window is 1 hour (`service.py` ~line 873). It is 45 minutes now.
- I did not inspect `4474af25` (logs the outcome of each instance) or `d2675cf4` (masks raw fields). Their subjects don't suggest they change the decision, but I did not read them.

----- next turn -----

**Cause:** `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). Before it, custom dedup windows were computed as `timedelta(minutes=f.window)`. That commit switched them to `_window_start(f.window)` and labelled the value as seconds. The UI still says "Window (minutes)" with options 5–30, so a 30 became a 30-second window. Two instances ten minutes apart fall well outside that, so they didn't group. The existing dedup tests use `window=5` with back-to-back instances, so they passed either way and didn't catch it.

**Fix** (`src/dispatch/signal/service.py`, `filter_dedup`): the custom-filter window now converts minutes to seconds before calling `_window_start`:

```python
# SignalFilter.window is entered in minutes
window = _window_start(f.window * 60)
```

Stored values are untouched, so existing filters work without edits. I also corrected the `SignalFilter.window` column comment in `src/dispatch/signal/models.py`, which still said seconds.

**Regression test** added: `test_filter_window_is_in_minutes` in `tests/signal/test_signal_service.py`. With `window=30`, a previous instance 10 minutes old should dedupe the new one, and with only a 40-minute-old instance in range it should not. Before the fix, the first assertion failed (`filter_signal` returned False). After the fix it passes.

**Results**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- Full suite: 8 tests fail, all in `tests/ai`, `tests/database` and `tests/entity`. I ran the suite on a stashed clean tree and the same 8 fail there, so they predate this change. My new test is not among them.

**Not changed, for you to decide**
- The column default in `models.py` is `60 * 60` and the Pydantic default is `600`. Both now mean minutes, so the column default would be 60 hours if it were ever used. I couldn't confirm whether any path relies on it. I left both alone.
- `filter_signal`'s docstring still says the default window is 1 hour. It is 45 minutes now.
- `086dc910` changed an expired snooze filter from `continue` to `break`, so later snooze filters on the same signal are skipped. That is separate from this bug and I left it as is.

----- next turn -----

**Cause:** commit `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). In `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter used to `continue` to the next filter. That commit changed it to `break`. So when the expired filter is listed first, the loop stops and the valid "until next month" filter is never checked. The new instance is not snoozed.

**Fix:** that expiry check now uses `continue` again, so expired filters are skipped and evaluation carries on:

```python
if f.expiration.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
    continue
```

**Regression test:** `test_filter_actions_snooze_after_expired_snooze` in `tests/signal/test_signal_service.py`. It sets up an expired snooze filter (7 days ago) followed by a valid one (30 days ahead), both matching the same entity, and asserts the instance is snoozed. It failed before the fix and passes now.

**Results:** `python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not re-run the full suite this time. The 8 failures in the earlier full run (in `tests/ai`, `tests/database` and `tests/entity`) were already present on the clean tree.

**Left alone:** `086dc910` also removed the warnings for a snooze filter with no mode or no action. Those filters are still skipped, just without a log line. That is not a decision change, so I didn't restore it.

----- next turn -----

Recap of this session's changes to snooze and dedup decisions, plus the uncommitted fixes:

- **Dedup window in minutes (fixed):** commit `917a0b7b` read custom dedup filter windows as seconds, although the UI sets them in minutes. Windows are now converted from minutes in `filter_dedup`. Regression test: `test_filter_window_is_in_minutes`.
- **Expired snooze stopped evaluation (fixed):** commit `086dc910` changed an expired snooze filter from `continue` to `break`, so later valid snooze filters were skipped. The check now uses `continue`. Regression test: `test_filter_actions_snooze_after_expired_snooze`.
- **Canary signals (unchanged this session):** commit `a348bbd2` excludes canary signals from deduplication, both as candidates and as matches.
- **Default grouping for filterless signals:** 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`).

The fixes are uncommitted in the working tree. Signal tests pass: 34 passed, 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES