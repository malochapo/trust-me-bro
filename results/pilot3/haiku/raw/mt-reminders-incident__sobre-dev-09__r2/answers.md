**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") added `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` in Python, but `isoweekday()` returns `1` for Monday. So the check is never true, and both weekly paths (`case_close_reminder` for triage at line 49 and `case_stable_reminder` for stable at line 95) never send. The daily triage reminder (`case_triage_reminder`) doesn't call this helper, which is why it still works. The original code compared against `1`, so the refactor changed behavior even though it looks equivalent.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to the scheduler and web pods on 2025-08-13 at 16:40Z (kubelet lines in both logs). `c509d45e` (2025-08-12 14:05 -0700, Jordan Lee) is an ancestor of `81d8ae42` (fix(case): exclude resolved_by in update, #6183), and the previous image `b05613b5` does not contain it.

**Timing in the logs:**
- Last Monday before the deploy was 2025-08-11, and the pre-deploy image had the old `== 1` check. The first Monday after the deploy was 2025-08-18, and that's when the reminders stopped.
- The scheduler's `case_stable_reminder` log lines stop erroring after 08-13. That's the `None` crash fixed in `32fa810f` (`fix(scheduler): not all cases have a stable_at date`), which shipped in the same deploy.
- The logs don't record successful reminder sends, so I couldn't confirm the missing sends directly. The timing and the calendar value are the evidence.

**Secondary issue (not the cause, but it will bite after the fix):** `case_close_reminder` reads `case.triage_at` at line 47 before the Monday check, and there's no `None` guard there. The 2025-08-18 log shows `TypeError ... 'NoneType'` at that line for some triage cases, so those cases are skipped even on Mondays. The stable path has a guard (`if case.stable_at:`), but the triage path doesn't.

I haven't changed any code. The likely fix is to compare against `1` (or `calendar.MONDAY + 1`) in `_is_reminder_day()`, and to add the same `None` guard to the triage path. I'd also add a test for `_is_reminder_day()` on a Monday, since the existing tests don't seem to cover the weekday branch.

----- next turn -----

The weekly reminders are fixed and there's a regression test for them. The new tests pass, and the test that reproduces the bug fails against the original code.

**The fix** (`src/dispatch/case/scheduled.py`)
- `_is_reminder_day()` now compares `isoweekday()` to `1`. The refactor had compared it to `calendar.MONDAY`, which is `0`, so the weekly triage and stable reminders never fired. I removed the `calendar` import.
- I also added a `if case.triage_at:` guard to the triage path of `case_close_reminder`, matching the stable path. I flagged this earlier as a separate issue. Without it, a triage case with no `triage_at` still raises inside the loop, so it would never get a weekly reminder even after the weekday fix. This goes slightly beyond the weekday bug you asked about, so say if you'd rather split it out.

**The regression test** (`tests/case/test_case_scheduled.py`, new)
- `test_is_reminder_day` covers all seven weekdays, with only Monday true.
- The stable and triage reminder tests check that a case stable or triaging for 8 days is sent on Monday and not on Tuesday.
- `test_reminders_skip_cases_without_timestamps` covers cases with a `None` `triage_at` or `stable_at`.
- The tests call the real task functions, looked up by name in `scheduler.registered_tasks`, with the day frozen by patching `date` in the module.
- I reintroduced the `== 0` bug temporarily and the test failed, then I restored the fix.

**Test results** (`python -m pytest`, PostgreSQL running locally)
- The new file: 10 passed.
- Full suite: 369 passed, 4 skipped, 8 failed, 1 error. The failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, `tests/entity/test_entity_service.py`, and `tests/workflow/test_workflow_service.py`. They're the same with and without my change, so they predate it. I didn't investigate them.

I haven't committed anything.

----- next turn -----

The close reminder's `TypeError` happens when a case is in `triage` but its `triage_at` is empty. The job now counts those cases from `created_at` instead, and a regression test covers it.

**Cause:** `triage_at` is only set by `case_triage_status_flow`, which runs when a case moves to triage from new or closed, or on creation. The status dispatcher's catch-all branch for `(_, triage)` logs a warning and skips it. So a case moved from stable or escalated to triage keeps `triage_at` empty. I reproduced this against the test database: both transitions leave `triage_at` as `None`.

Caveat: the API and scheduler logs don't name the affected case, and the "Unexpected previous state" warning doesn't appear in them. So I couldn't confirm which transition happened in production. This is the only path I found that leaves a triage case without `triage_at`. The error appears every evening from 2025-07-28, so the case has likely been stuck since then.

**Changes**
- `src/dispatch/case/scheduled.py`: `case_close_reminder` now counts from `case.triage_at or case.created_at`. I removed the `if case.triage_at:` guard I added earlier, since that version skipped these cases instead of counting them.
- `tests/case/test_case_scheduled.py`:
  - A triage case with no `triage_at` and created 8 days ago gets its reminder on Monday.
  - A triage case with no `triage_at` created 3 days ago does not.
  - A stable case with no `stable_at` is still skipped.
  - The fallback test fails when the fallback is removed.
- All 12 tests in that file pass.

**Full suite:** 371 passed, 4 skipped, 8 failed. The 8 failures are the same unrelated ones as before my changes (`tests/ai`, `tests/database`, `tests/entity`). An earlier run also had one error in `tests/workflow/test_workflow_service.py`, which didn't come back in this run.

**Not changed:**
- The catch-all branch in `case_status_transition_flow_dispatcher` still doesn't set `triage_at`. Setting it there would fix the data going forward, but it changes what `triage_at` means for those transitions, so I left it for you to decide.
- The stable reminder still skips cases with no `stable_at`. You scoped this fix to the close reminder, so I didn't change it.

I haven't committed anything.

----- next turn -----

## Recap

**Weekly reminder outage.** Since mid-August, assignees didn't get the Monday reminders for long-running triage and stable cases. Daily triage reminders kept working.

- **Cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The refactor compared `date.today().isoweekday()` to `calendar.MONDAY`, which is `0` in Python. `isoweekday()` returns `1` for Monday, so the check was never true and no weekly reminders were sent.
- **Deploy:** Image `registry.example.com/dispatch:main-81d8ae42`, rolled out 2025-08-13 at 16:40Z. It contains `c509d45e`. The Monday before it, 2025-08-11, ran the old code and was fine.
- **Fix:** `_is_reminder_day()` compares to `1`. Covered by a regression test that fails on the buggy code.

**Evening TypeError.** The case close reminder logged `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` every evening from 2025-07-28. Some triage cases had no `triage_at`. Moving a case from stable or escalated to triage does not set it, because the status dispatcher's catch-all `(_, triage)` branch skips the timestamp. I reproduced that in the test database. The logs don't name the affected case, so I couldn't confirm which transition happened in production.
- **Fix:** The close reminder counts from `triage_at`, falling back to `created_at`. Covered by tests, including one that fails without the fallback.
- **Not changed:** The catch-all branch still doesn't set `triage_at`. Fixing it changes what `triage_at` means for those transitions, so that's a call for the team.

**Tests:** The reminder test file passes (12 tests). The full suite has 8 failures in `tests/ai`, `tests/database`, and `tests/entity`. These are the same before and after my changes and look unrelated. One workflow test error from an earlier run did not recur.

Nothing is committed.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```