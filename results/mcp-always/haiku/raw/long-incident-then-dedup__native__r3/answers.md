**Root cause:** `_is_reminder_day()` compares ISO weekday to the wrong constant, so it is never true. Nothing else in the reminder config changed.

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (`calendar` numbers the week from Monday = 0). I confirmed both values with Python. So the check is only true on a day that is both Monday and weekday 0, which never happens. Both weekly paths call it: `case_close_reminder` (triage cases, line 49) and `case_stable_reminder` (stable cases, line 95). The daily triage and incident reminders don't use it, which is why they still arrive.

**The commit that introduced it:** `c509d45e` (2025-08-12, Jordan Lee, "refactor(case): share the weekly reminder check"). It replaced the literal `date.today().isoweekday() == 1` with `_is_reminder_day()` and used `calendar.MONDAY` instead of `1`. The old literal was correct.

**The deploy that shipped it:** the scheduler container started on image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40:06Z (`scheduler.log:18851`). That is `81d8ae42`, "fix(case): exclude resolved_by in update (#6183)", committed 2025-08-12 14:47 -0700. `c509d45e` is an ancestor of it. The web container was redeployed from the same tag at 16:40:07Z. This assumes the short SHA in the image tag maps to the commit, which is the usual convention.

**Logs agree with the timeline:**
- Mon 2025-08-04: case close reminders sent (old image).
- Mon 2025-08-11: case close reminders sent, from scheduler `xdp7k6gs2q` on image `main-b05613b5`, which predates `c509d45e`.
- Tue 2025-08-12 onward: triage reminders keep going out daily.
- Mon 2025-08-18: no case close reminders sent. The first missed Monday.

**Things I noticed but did not change:**
- The `NoneType` errors in `case_stable_reminder` in the logs stop being relevant after `32fa810f` (2025-08-11), which added the `if case.stable_at:` guard. The guard is there in the current code.
- `case_close_reminder` has a similar `NoneType` error on `triage_at` (`scheduler.log:791`, 2025-07-28). It is caught per case, but it still means some cases are skipped. Worth checking separately.
- `incident/scheduled.py:229` uses the literal `1`, so it isn't affected.
- No tests reference `_is_reminder_day`, `case_close_reminder`, or `case_stable_reminder`, so the regression wasn't caught.

**Suggested fix (not applied):** use `date.today().weekday() == calendar.MONDAY`, which is 0-based and matches `calendar.MONDAY`. Or revert to `isoweekday() == 1`. Either way, add a unit test that pins a known Monday, so this kind of mismatch fails in CI.

No files were changed.

----- next turn -----

The fix is in and the regression test is added. Nothing is committed.

**Fix** (`src/dispatch/case/scheduled.py:33`): `date.today().isoweekday() == calendar.MONDAY` became `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar.MONDAY`, so the comparison now matches Monday.

**Regression test** (`tests/case/test_case_scheduled.py`, new): a parametrized test that patches `date.today()` to each day of one week (2025-08-11 to 08-17) and asserts `_is_reminder_day()` is True only on Monday.

**Verification:**
- With the fix, `python -m pytest tests/case/test_case_scheduled.py` passes all 7 cases.
- With the original line put back temporarily, the Monday case fails. So the test would have caught this.
- `python -m pytest tests/case` passes all 22 tests. I did not run the full suite.

I did not add a test that drives `case_close_reminder` or `case_stable_reminder` end to end. That would need database fixtures and the scheduler decorators, and the unit test covers the broken expression directly.

----- next turn -----

The close reminder now falls back to `created_at` when `triage_at` is missing, so those cases get their Monday reminder. Tests pass (`python -m pytest tests/case`: 25 passed). Nothing is committed.

**Cause of the nightly `TypeError`:** `case_close_reminder` subtracts `case.triage_at` from the current time. `triage_at` is only stamped in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427` sets `case.status = CaseStatus.triage` directly, without running that flow, so `triage_at` stays empty. The subtraction raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`, and the per-case `try/except` logs it and skips the case. That is 24 entries in `scheduler.log`, from 2025-07-28 to 2025-08-20. I can't tell from the logs which case was reopened; this is the only code path I found that puts a case into triage without stamping `triage_at`.

**Fix** (`src/dispatch/case/scheduled.py:47-50`):
```python
triaged_since = case.triage_at or case.created_at
span = datetime.utcnow() - triaged_since
```
`triage_at` is still used when present.

**Tests** (`tests/case/test_case_scheduled.py`, added alongside the earlier ones):
- A case with no `triage_at` and created 8 days ago gets a reminder. This is the regression test; I confirmed it fails with the old line and the same `TypeError` appears.
- A case with no `triage_at` created 3 days ago gets no reminder.
- A case with `triage_at` set uses it, even if `created_at` is more recent.

The tests call the job the scheduler registers, with the decorators stripped so they don't open sessions against every organization schema. `scheduler.add` returns `None`, so the test looks the job up in `scheduler.registered_tasks`.

**Not changed, for you to decide:**
- The stable reminder still skips cases with no `stable_at` instead of counting from `created_at`. You scoped this to the close job, so I left it.
- The reopen handler also skips the transition flows, so whatever the closed→triage flow does is skipped too. Fixing that is a separate change; I can make it if you want.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed how signal instances are snoozed or deduplicated. Two of them change the time windows. Nothing was modified.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - Canary instances skip deduplication. They are also excluded as dedup candidates in both the default branch and the per-filter branch.
   - No time window changed.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*
   - The default window (used when a signal has no dedup filter) was hard-coded at 1 hour. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`).
   - Today's value: **45 minutes** (2700 seconds). It is matched against `SignalInstance.created_at`, and only instances with a case are considered.
   - The docstring of `filter_signal` still says "1-hour window".

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - This is the only commit that changed snooze logic. The mode and action checks are merged, and the warning logs for missing mode or action are removed.
   - It also changes an expired snooze filter from `continue` to `break`. Before, an expired filter was skipped and later snooze filters on the signal were still checked. Now the loop stops at the first expired one. The commit message doesn't mention this.
   - Snoozes have no time window. They end at the filter's `expiration` timestamp.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Adds `_window_start(seconds)` (`src/dispatch/signal/service.py:784`).
   - The per-filter dedup window was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as **seconds**. The `SignalFilter.window` column is documented as seconds (default 3600, `src/dispatch/signal/models.py:206`), so the new code matches the model.
   - The UI does not match. `SignalFilterCreateDialog.vue` labels the field "Window (minutes)" with options 5, 10, 15, 20, 30. I found no conversion before submit, so a filter created in the UI with 30 now dedups over **30 seconds**, not 30 minutes. The Pydantic default of 600 also now means 10 minutes, not 10 hours.
   - I did not check production data, so I can't say how many filters are affected.

**Excluded:** `4474af25` (logs filter outcome), `d2675cf4` (masks raw fields), and `5e136d7b` (UI snooze view) don't change the decision logic.

**Decision for you:** Is the filter window meant to be seconds (as the model says) or minutes (as the UI says)? If it's minutes, `917a0b7b`'s unit change is the regression, and I'd restore the minute conversion for filters while keeping `_window_start`. I'd also want to check whether the `086dc910` `break` was intended.

----- next turn -----

The cause was commit `917a0b7b` (2025-08-14, *share the lookback window computation*). It changed the per-filter dedup window from minutes to seconds. A window of 30 became 30 seconds, so two instances ten minutes apart were never grouped. The UI and existing filters both store minutes, so the backend now reads them that way again.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. Filter windows use `_window_start(f.window)`, and the default dedup window uses `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES)`.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default is now `60` and the comment says minutes. The Python-side default means no migration is needed. Existing rows keep their stored values, so existing filters work without editing.
- `tests/signal/test_signal_service.py`: two regression tests.
  - A 30-minute filter groups an instance that is 10 minutes old. This is the reported case, and it fails with the seconds unit.
  - A 30-minute filter ignores an instance that is 40 minutes old.

**Tests**
- `python -m pytest tests/signal tests/case`: 59 passed, 1 skipped.
- Full `python -m pytest`: 371 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way with my changes stashed, so they predate this work. I didn't investigate them.

**Left alone, for you to decide**
- `SignalFilterBase.window` in `models.py` still defaults to `600`. Under minutes, an API-created filter that omits `window` now dedups over 10 hours, not 10 minutes. The UI always sends a value, so this only affects API callers. I can change it to `60` if you want the 1-hour default.
- The `filter_signal` docstring still says "1-hour window" for the default. The default is 45 minutes.
- The `086dc910` change from `continue` to `break` on expired snooze filters is unrelated to windows and is unchanged.

Nothing is committed.

----- next turn -----

The cause was commit `086dc910` (2025-08-07, *simplify snooze filter checks*). It changed the expired-filter branch in `filter_snooze` from `continue` to `break`. When the expired filter came first in the list, the loop stopped there, so the valid one never got checked. That matches the report: the expired snooze was the one that stopped evaluation.

**Fix:** `src/dispatch/signal/service.py:763` is back to `continue`, so an expired filter is skipped and the loop goes on to the next one.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It puts an expired snooze filter for the entity before a valid one (expires in 30 days) and asserts the instance is snoozed. With `break` restored, the test fails; with the fix, it passes.

**Tests**
- `tests/signal` and `tests/case`: 60 passed, 1 skipped.
- Full `python -m pytest`: 372 passed, 8 failed, 4 skipped. The same 8 unrelated failures as before (`tests/ai`, one in `tests/database`, one in `tests/entity`) fail without my changes too.

**Still open:**
- This is the `break` from `086dc910`, not the window unit fix from `917a0b7b`. The window fix is still in place.
- The `086dc910` change also removed the logs for filters with no mode or action. Those checks are covered by the `mode`/`action` comparison, so behavior is the same, but no warning is logged anymore. I left that alone.

Nothing is committed.

----- next turn -----

## Weekly report: today's work

**Weekly Monday reminders (investigation 1)**
- Assignees stopped getting the weekly reminders to close long-running triage and stable cases. `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced this, and it shipped on the scheduler in image `main-81d8ae42` on 2025-08-13. The logs show 5 close reminders on Monday 2025-08-11 (before the deploy) and none on Monday 2025-08-18.
- Fixed to `date.today().weekday() == calendar.MONDAY`. A parametrized test covers Monday through Sunday, and the old code fails it.

**Nightly TypeError (investigation 2)**
- `case_close_reminder` subtracted `case.triage_at` from the current time, but `triage_at` is empty for cases put back into triage through the Slack reopen button (`reopen_button_click`, which skips the flow that stamps it). The subtraction raised a TypeError, which the per-case handler logged and skipped. The logs show it every evening from 2025-07-28 onward.
- Fixed by counting from `triage_at or created_at`. Three tests cover the fallback, the recent-case skip, and the `triage_at` preference. I could not tell from the logs which cases were affected, and I did not verify this against production data.

**Filter windows, snoozes, and canary signals (investigations 3–5)**
- **Deduplication windows:** commit `917a0b7b` changed the filter window from minutes to seconds. The UI and existing filters store minutes, so a 30-minute window became 30 seconds. Fixed so the backend reads the window in minutes again, with the column default changed to 60 (minutes). Existing filters work without edits. Two regression tests cover the 10-minute and 40-minute cases.
- **Snoozes:** commit `086dc910` changed the expired-filter branch from `continue` to `break`. An expired snooze listed first stopped evaluation of the valid ones after it. Fixed back to `continue`, with a regression test that fails under `break`.
- Full suite: 372 passed, 8 failed. The 8 failures are in `tests/ai`, `tests/database`, and `tests/entity`, and they fail on the original code too.

**Not committed.** The changes are in the working tree: `src/dispatch/case/scheduled.py`, `src/dispatch/signal/service.py`, `src/dispatch/signal/models.py`, `tests/signal/test_signal_service.py`, and the new `tests/case/test_case_scheduled.py`.

**Left open:**
- `SignalFilterBase.window` in `models.py` still defaults to 600, which now means 10 hours for API-created filters that omit the field.
- The stable reminder still skips cases with no `stable_at`, and the reopen handler still bypasses the transition flows.

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