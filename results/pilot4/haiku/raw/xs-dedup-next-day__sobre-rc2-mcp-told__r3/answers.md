Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or changed the windows it uses. I read the code and history only and changed nothing.

The current windows, as the code applies them:
- **Default dedup window** (no dedup filter on the signal): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES × 60`, so 45 minutes (2700 seconds). Set in `src/dispatch/config.py:95`.
- **Custom dedup filter window**: `SignalFilter.window` in seconds, used directly. The model default is 3600 (1 hour) and the API schema default is 600 (10 minutes). See `src/dispatch/signal/models.py:206` and `:282`.
- **Snooze**: no time window. A snooze applies until its `expiration` timestamp.

The commits, oldest first:

1. **`a348bbd2`** (2025-05-29, "fix(signal): don't dedup on canary signals (#6026)"): canary signal instances are skipped by dedup. Canaries are also excluded from the candidate matches, so they never match other instances. At this commit, the default window was still hard-coded at 1 hour.

2. **`7a9fe810`** (2025-06-19, "feat(signal): make the default deduplication window configurable"): the default window moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.

3. **`086dc910`** (2025-08-07, "refactor(signal): simplify snooze filter checks"): this is a behaviour change, not only a refactor. An expired snooze filter used to `continue`, so later filters were still checked. It now `break`s, so no further snooze filters are evaluated. The commit also removed the warning logs for filters with no mode or no action. The mode and action checks still skip such filters, so behaviour there is unchanged.

4. **`917a0b7b`** (2025-08-14, "refactor(signal): share the lookback window computation"): this changed the unit of the custom dedup window. The old code computed `timedelta(minutes=f.window)`. The new code computes `_window_start(f.window)` with the value treated as seconds, and the comment says "SignalFilter.window is stored in seconds". Any existing filter that stored a window in minutes is now 60 times shorter. For example, a stored 600 used to mean 10 hours and now means 10 minutes.

Things to check:
- The `filter_signal` docstring and the model comment still say the default window is 1 hour. The code uses 45 minutes.
- If `f.window` is `None`, `_window_start(None)` will fail. The API schema allows `None`.
- I did not check whether existing rows in the database were migrated when `917a0b7b` changed the unit. If they weren't, live filters are now using the new unit against old values.

I also checked the other commits that touch the signal code: `5e136d7b`, `4474af25`, `d2675cf4`, `90f73fe2`, `dee1699d` and `01c28ff0`. None of them changes the snooze or dedup logic. `4474af25` only logs the filter outcome.

I recorded the finding in the sobre session.

----- next turn -----

The window bug came from `917a0b7b` (refactor, 2025-08-14). It is fixed, and a regression test covers it.

**Cause:** Before `917a0b7b`, `filter_dedup` computed the lookback as `timedelta(minutes=f.window)`, which matches the UI's "Window (minutes)" field (options 5–30). That commit replaced it with the shared `_window_start(f.window)` helper, which takes seconds, and added a comment saying the window is stored in seconds. Every existing filter's window therefore shrank 60×. A 30-minute filter became 30 seconds, so two instances ten minutes apart no longer grouped.

**Fix:**
- `src/dispatch/signal/service.py`: the filter path now calls `_window_start(f.window * 60)`, and the comment says the value is stored in minutes. No data migration is needed, so existing filters work unedited.
- `src/dispatch/signal/models.py`: corrected the comment to minutes and changed the column default from `60 * 60` to `60`, so the default still means one hour.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes`. It creates an earlier instance with a case, ten minutes old, and a deduplicate filter with `window=30`, then asserts the new instance joins that case. I confirmed it fails with the buggy line restored and passes with the fix.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped against PostgreSQL.

**Things I did not change:**
- The Pydantic `SignalFilterBase.window` default is still `600`, which under the minutes unit is 10 hours. It only applies when the API omits the field, so I left it alone; say if you want it changed to 60.
- The `ruff format --check` complaint on `models.py` existed before my change.
- The 2025-05-22 commit list was not in my context, so I rebuilt it from `git log`. The dedup/snooze-related commits were `a348bbd2`, `7a9fe810`, `086dc910`, and `917a0b7b`. Only `917a0b7b` touches the window arithmetic.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES