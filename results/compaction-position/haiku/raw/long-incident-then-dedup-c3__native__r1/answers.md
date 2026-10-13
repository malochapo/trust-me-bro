The root cause is an off-by-one in a helper added by `c509d45e`: `calendar.MONDAY` is `0` in Python, but `isoweekday()` returns `1` for Monday, so the Monday check is never true. The code shipped to production in image `main-81d8ae42`, which started on both the web and scheduler pods at 2025-08-13 16:40Z. I didn't change any code.

**The bug**

`src/dispatch/case/scheduled.py:31-33`, added in `c509d45e` (Jordan Lee, 2025-08-12 14:05 -0700, "refactor(case): share the weekly reminder check"):

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The commit replaced `date.today().isoweekday() == 1` with this helper. The `1` was correct; `calendar.MONDAY` is `0` (Monday-based week numbering, Monday = 0), while `isoweekday()` is ISO-based (Monday = 1). I checked both values in the sandbox: `calendar.MONDAY = 0`, `isoweekday(2025-08-18) = 1`. So `_is_reminder_day()` always returns `False`, and both weekly paths are dead:

- `case_close_reminder` (triage cases, line 49)
- `case_stable_reminder` (stable cases, line 95)

The daily `case_triage_reminder` doesn't call the helper, which matches your observation that the daily triage reminders still arrive.

**Evidence in the logs**

- Before the deploy, the Monday reminders worked. On 2025-08-11 (Monday) the scheduler log shows "Case close reminder sent" for several assignees.
- The old image was `main-b05613b5` (deployed 2025-07-30). It doesn't contain `c509d45e`.
- The new image `main-81d8ae42` started at 2025-08-13 16:40Z on both `web-5dkmr9s9s-xxktx` (api.log:13201) and `scheduler-mhtsgqwwx-q5q2n` (scheduler.log:18851). It is the only deploy in the window. `c509d45e` is an ancestor of `81d8ae42`, and `81d8ae42` is the `main` tip that was built into that image.
- The first Monday on the new image is 2025-08-18. The log has no "Case close reminder sent" lines that day, and the stable reminder runs silently. This is the first missed Monday.

**Other things I noticed (not the cause)**

- From 2025-08-12 to 08-13, `case_stable_reminder` crashed on every run because `case.stable_at` was `None`. That was fixed by `32fa810f` (08-11), which is included in `81d8ae42`, so it's no longer happening.
- Since 2025-08-13 18:00Z, `case_close_reminder` logs a `TypeError` on `case.triage_at` being `None` for some triage cases. The per-case `try/except` catches it, so other cases still run. Those cases will never get a triage reminder until they have a `triage_at` value. This is a separate issue.

**Suggested fix (not applied)**

Change `_is_reminder_day()` to compare against `1`, or use `calendar.MONDAY + 1` / `datetime.isoweekday` with an explicit constant. Add a test that asserts `_is_reminder_day()` is true on a known Monday. Note that the Monday reminders will only come back on the next Monday after the fix ships, and any cases that were skipped won't be backfilled.

----- next turn -----

The weekly Monday reminders are fixed, and a regression test covers the bug. Nothing is committed.

**The fix** (`src/dispatch/case/scheduled.py`)
- Removed the `calendar` import.
- `_is_reminder_day()` now compares `date.today().isoweekday()` against `1`, with a comment on why. `calendar.MONDAY` is `0`, so the old check never matched.
- Both `case_close_reminder` and `case_stable_reminder` already call this helper, so both are fixed by this one change.

**The regression test** (`tests/case/test_case_scheduled.py`, new)
- Parametrized over the seven days of the week 2025-08-11 to 08-17, with `date.today` patched. It asserts that only Monday returns `True`.
- The original code fails the Monday case and passes the other six. The fixed code passes all seven.
- I didn't add a test that runs the full scheduled tasks. The helper is the only part that changed, and the test pins it directly.

**Verification**
- `python -m pytest tests/case -q`: 22 passed, including the 7 new tests.
- `ruff check` and `ruff format --check` on both files: clean. (Ruff was available via `python -m ruff`; the bare `ruff` command isn't on the PATH.)
- I didn't run the full test suite.

**Still open**
- The fix only takes effect after it ships. The next Monday reminders will go out on the first Monday after the deploy. The reminders skipped since 2025-08-18 won't be sent later.
- The separate `triage_at = None` error in `case_close_reminder` is still there. It's caught per case, so it doesn't stop the other cases, but cases with no `triage_at` won't get reminders. I didn't change it, since it's outside this fix.

----- next turn -----

The triage reminder job no longer errors on cases with no `triage_at`. Such cases now count from `created_at`, and the fix has a regression test. Nothing is committed.

**What causes the TypeError**

`triage_at` was added to the `case` table in the 2022-08-01 migration (`2022-08-01_391f7c3e6992.py`) with no backfill. Every case that entered triage before that date has `triage_at = NULL`. The job does `datetime.utcnow() - case.triage_at`, which raises `TypeError` for those rows. The per-case `try/except` catches it, so the other cases still run.

The logs match this: the `TypeError` appears once per evening, every day from 2025-07-28 through 08-20. Those are the only stack traces at `scheduled.py` line 47.

I couldn't check the production database, so this is inferred from the migration and the logs, not confirmed against the rows. Two other paths can also leave `triage_at` empty: the `(_, triage)` fallback branch in `flows.py` and the Slack handlers that set `status = triage` directly. The logs have no "Unexpected previous state" warnings, so I don't think they are the source of these errors.

**The fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`)

```python
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

A comment explains why the fallback exists. `created_at` has a default, so it is set on every case.

**The test** (`tests/case/test_case_scheduled.py`)

`test_case_close_reminder_falls_back_to_created_at` creates two triage cases in one project:
- one with no `triage_at` and `created_at` 14 days ago. It should get a reminder.
- one with `triage_at` 1 day ago and `created_at` 14 days ago. It should not, because `triage_at` takes precedence.

The test runs the real job against the test session. It finds the job in `scheduler.registered_tasks` and unwraps it, because the module-level name is `None`. It patches the reminder send and the Monday check.

**Verification**
- Without the fallback, the test fails with `assert [] == [10]`. With the fix it passes.
- `python -m pytest tests/case -q`: 23 passed.
- `ruff check` and `ruff format --check` pass on both files.

**Not changed**
- `case_stable_reminder` skips cases with no `stable_at` (`if case.stable_at:`, added in `32fa810f`). Those cases never get stable reminders. You only asked about the triage job, so I left it. The same fallback would work there, using `created_at`, if you want it.
- The fallback doesn't backfill `triage_at`. Old cases will keep counting from creation, which is the behavior you asked for.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed the snooze or dedup decision. One of them, `917a0b7b`, silently changed how filter dedup windows are measured, and the UI's "Window (minutes)" choices are now read as seconds.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - `filter_dedup` returns early for canary instances.
   - Canary instances are excluded from the match query, both in the default path and in the filter path.
   - No window change.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*
   - Before: signals with no dedup filter used a hard-coded `timedelta(hours=1)`, which is 60 minutes.
   - Now: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, read as minutes, default **45 minutes** (2700 s). Any deployment that doesn't set the variable gets 45 instead of 60.

3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*
   - Merged the mode and action checks into one `continue` condition. The removed "has no mode / has no action" warnings don't change the outcome, since `None` already fails the check.
   - **Behavior change:** when a snooze filter has expired, the loop was `continue` and is now `break` (`service.py` ~line 763). Any later active snooze filter on the same signal is no longer checked for that instance. The result depends on the order of `signal.filters`, which I did not verify.
   - No window change.

4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*
   - Added `_window_start(seconds)`.
   - Default path: still 45 minutes, now computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. Same value.
   - Filter path: changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, so **`SignalFilter.window` is now read as seconds**. The model comment has said seconds since 2023 (`models.py:206-208`), so the code now matches the model, but it did not match the code before this commit.
   - Effects today:
     - Model column default `3600` → 1 hour (correct as seconds).
     - API schema default `600` (`models.py:282`) → 10 minutes. Before, it was 600 minutes.
     - UI: `SignalFilterCreateDialog.vue:57-58, 196` labels the field "Window (minutes)" with options `[5, 10, 15, 20, 30]`. The value is sent without conversion, so a "10 minute" choice now dedups over **10 seconds**, 60 times shorter than the user chose.
   - Existing filters that were stored in minutes keep their numbers, so they also shrink by 60x.
   - The tests use `window=5` and I did not check whether they still pass.

**Not affecting the decision:** `d2675cf4` (masks raw fields before processing) and `4474af25` (logs the filter outcome). I didn't check whether masking changes what expressions match.

**Current behavior**
- Snooze: applies if the signal has an active snooze filter whose expiration is in the future and whose expression matches the instance (no expression means it snoozes everything). The check stops at the first expired snooze filter (see 3).
- Dedup with no dedup filter: 45 minutes by default, by `created_at`, against instances that have a case. Canary instances are excluded.
- Dedup with dedup filters: `window` in seconds, from `created_at`, matched on shared entities. Canary instances are excluded.

I made no code changes and didn't run the tests. Fixing the UI unit mismatch would be a decision for you: either convert in the UI (`* 60`) or change the backend back to minutes and migrate existing rows.

----- next turn -----

Fixed. The cause was `917a0b7b` (2025-08-14). It changed the filter window from minutes to seconds, so a window of 30 became 30 seconds. Your two instances were 10 minutes apart, so they never matched and opened two cases.

**The fix**

- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The filter window is read as minutes, as the UI labels it, and the default dedup window uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly. The 08-14 refactor (shared helper) is kept.
- `src/dispatch/signal/models.py`: the `window` comment now says minutes. I changed only the comment, not the values.

Existing filters work without edits because the UI has always stored minutes. Nothing was migrated.

**The regression test**

`test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It creates an instance with a case 10 minutes ago, then a new instance for the same entity, with a window of 30. The new instance must be deduplicated onto that case. It fails with the seconds unit and passes with the fix.

**Verification**
- `python -m pytest tests/signal -q`: 33 passed, 1 skipped.
- `python -m pytest tests/case -q`: 23 passed.
- `ruff check` passes on the changed files.

**Decisions for you**

- The column default (`60 * 60`) and the API schema default (`600`) are unchanged. Read as minutes, they mean 60 hours and 10 hours. Both were already minutes before 08-14, so I left them. You may want to change them to 60 and 600 is wrong too; say if you want that.
- Any filter saved through the API between 08-14 and now used seconds, so it is now 60 times longer than the value it was given. I can't tell which filters those are from the code. Check whether any API clients set `window`.

Nothing is committed. My earlier `scheduled.py` changes are still in the working tree.

----- next turn -----

Fixed. The cause was `086dc910` (2025-08-07, "simplify snooze filter checks"). When it turned an expired snooze filter's `continue` into `break`, the loop in `filter_snooze` stopped at the first expired filter and never reached the valid one behind it. For the Okta signal, the expired filter came first, so new instances for that user were not snoozed.

**The fix** (`src/dispatch/signal/service.py`, line 763)

The expired check is back to `continue`, so the loop skips expired filters and keeps checking the rest.

**The regression test**

`test_filter_action_snooze_with_expired_filter_first` in `tests/signal/test_signal_service.py`. It appends an expired snooze filter, then a valid one that matches the same entity. The instance must be snoozed.
- With `break`, the test fails.
- With `continue`, it passes.

**Verification**
- `python -m pytest tests/signal tests/case -q`: 57 passed, 1 skipped.
- `ruff check` and `ruff format --check` pass on the changed files.

**Notes**
- The test depends on `signal.filters` returning filters in the order they were appended, because the relationship has no explicit ordering. The bug only appears when an expired filter comes first, so the test covers that order. The fix doesn't depend on order.
- Nothing is committed.

----- next turn -----

Here is today's recap. Everything below was checked against the repo and logs, except where I note otherwise.

**Investigation 1: missing Monday reminders**

Weekly case-close and case-stable reminders stopped after mid-August, while daily triage reminders kept arriving. The cause is an off-by-one in the weekday check. `calendar.MONDAY` is 0, but `date.isoweekday()` returns 1 for Monday. The check compared the two, so it was never true. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") introduced it. It shipped in image `main-81d8ae42`, which the `scheduler` container started on 2025-08-13 at 16:40 UTC. The 2025-08-11 Monday ran on the previous image, so the first missed Monday is 2025-08-18. The logs don't record individual reminder sends, so that date comes from the deploy time and the code path rather than from a direct log line. The fix changes the check to `isoweekday() == 1` and adds a regression test that fails on the old code. It is in the working tree, not yet deployed.

**Investigation 2: the case-close TypeError every evening**

The job logged a `TypeError` every evening from 2025-07-28 through 2025-08-20. The cause is cases with no `triage_at`. That column was added in the 2022-08-01 migration with no backfill, so cases that entered triage earlier have `NULL`. The job subtracted it from `utcnow()`. The fix counts from `created_at` when `triage_at` is missing, and a regression test covers it. I could not check the production rows, so this is inferred from the migration and the logs.

**Investigation 3: signal dedup and snooze** (reported in this session, not in the summary above)

- Deduplication windows: `917a0b7b` (2025-08-14) read filter windows as seconds, not minutes, so a 30-minute window became 30 seconds. The fix restores minutes. The regression test is `test_filter_actions_deduplicate_window_is_in_minutes`.
- Snoozes: `086dc910` (2025-08-07) changed the expired-snooze `continue` to `break`, so one expired snooze stopped the check for later valid snoozes. The fix restores `continue`. The regression test is `test_filter_action_snooze_with_expired_filter_first`.
- Canary dedup: `a348bbd2` (2025-05-29, "don't dedup on canary signals") excluded canary signals from deduplication.
- Default window: signals with no filter group over 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Before `7a9fe810` (2025-06-19) it was hard-coded at 60 minutes.

Nothing is committed. The working tree holds all the fixes and tests above. Two open issues: the default filter window (`3600`) and the API default (`600`) are read as minutes but are still large, and filters saved through the API between 2025-08-14 and today may have seconds values that now group 60 times more than intended.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```