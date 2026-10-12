**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check and broke it. The Monday gate is now `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, since Python's `calendar` numbers the week from Monday = 0. `isoweekday()` numbers Monday as `1`. So on Monday the expression is `1 == 0`, which is always false, and neither the triage close reminder (`case_close_reminder`, line 49) nor the stable reminder (`case_stable_reminder`, line 95) ever sends. The code before the refactor was `date.today().isoweekday() == 1`, which was correct. The refactor replaced the literal with the wrong constant.

The daily triage reminder (`case_triage_reminder`) doesn't use `_is_reminder_day()`, which is why it keeps arriving.

**Logs confirm it:**
- Monday 2025-07-28, 08-04 and 08-11 each sent 4–6 close reminders. Monday 2025-08-18 sent none.
- Triage reminders kept firing daily through 08-20.
- The logs end on 08-20, so I can't see whether Mondays after that are also affected. The code path says they are.

**The deploy:** `main-81d8ae42` (commit `81d8ae42`, "fix(case): exclude resolved_by in update", #6183), rolled out to both the scheduler and the web pods on **2025-08-13 at 16:40 UTC**. `c509d45e` is an ancestor of `81d8ae42` and is not in the previous image, `main-b05613b5`, which ran from 07-30 until that rollout. The first affected Monday is therefore 08-18. The 08-11 sends happened before the rollout, so they were fine.

**Secondary notes (not the cause):**
- `case_stable_reminder` crashed daily from 07-28 on cases with a null `stable_at`. `32fa810f` (08-11) added the `if case.stable_at:` guard and is also in the 08-13 image, so that crash is gone.
- `case_close_reminder` still does `datetime.utcnow() - case.triage_at` without a guard (line 47). Cases with null `triage_at` are logged as errors each day but skipped per case, so it's noise, not the outage.

I haven't changed any code. The likely fix is to restore `date.today().isoweekday() == 1` in `_is_reminder_day()`, or use `calendar.MONDAY + 1`. Missed Monday reminders for 08-18 and later probably won't be resent automatically, so you may want to decide whether to backfill them.

----- next turn -----

The reminder bug is fixed and a regression test is in place. The full suite still has 8 failures, but they fail identically on clean `main`, so my change didn't cause them.

**The fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` checks `isoweekday() == 1` again, which is Monday in ISO numbering. I removed the `calendar` import, since it's no longer used.

**The regression test** (`tests/case/test_case_scheduled.py`, new file): a parametrized test that patches `date.today` and checks `_is_reminder_day()` for each day of one week, with only Monday returning true. To confirm it catches the bug, I temporarily changed the check back to `== 0` (the `calendar.MONDAY` value). The Monday case failed and the other six passed. I then restored the fix.

**Test results:**
- The new test file: 7 passed.
- The full `python -m pytest` run: 366 passed, 4 skipped, 8 failed.
- The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those 8 on clean `main`, and they fail the same way. I didn't investigate their causes.

Nothing is committed. The working tree has the two changes above, and the scheduler will pick up the fix when it's deployed. Missed Monday reminders from 2025-08-18 onward won't be resent automatically.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and the new test covers it. The full suite still has the same 8 failures that predate my changes.

**What causes the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some cases are in triage status with `triage_at` NULL. That's the `NoneType` in the log. The per-case `try` catches it, so the job logs it and moves on to the next case. The 40 occurrences in the scheduler log are these per-case failures.

`triage_at` is only stamped by `case_triage_status_flow`, which runs on the flow transitions into triage. Some code paths set `case.status = CaseStatus.triage` directly and skip the flow. The clearest is the reopen button handler (`src/dispatch/plugins/dispatch_slack/case/interactive.py`, around line 1427). I didn't confirm which path created the affected cases. The logs don't record case IDs, and I have no database access.

**The fix** (`src/dispatch/case/scheduled.py`): the job counts from `case.triage_at or case.created_at`. A case with `triage_at` set behaves as before.

**The test** (`tests/case/test_case_scheduled.py`): four new cases run the close-reminder task on a Monday, using mocked data. A case with no `triage_at` created 9 days earlier gets a reminder. One created 2 days earlier doesn't. A case with `triage_at` set still follows `triage_at`. Without the fix, the first case reproduces the exact `TypeError` from the logs. With it, all 11 tests in the file pass.

**Full suite:** 370 passed, 4 skipped, and the same 8 failures as before, all in the `ai`, `database`, and `entity` tests that also fail on clean `main`.

Nothing is committed. I didn't change the paths that leave `triage_at` unset. The reopen button handler is the likeliest source, and fixing it would be a separate change.

----- next turn -----

**Recap**

- **Weekday bug:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which compares against `calendar.MONDAY`. That constant is `0`, so the Monday check could never be true. The weekly close reminders for triage and stable cases stopped sending. The daily triage reminders kept going because they don't use this check.
- **Deploy:** Image `main-81d8ae42` rolled out to the scheduler and web pods on 2025-08-13 at 16:40 UTC. The commit is in that image and not in the previous one, `main-b05613b5`.
- **Evidence:** Close reminders went out on Mondays 07-28, 08-04 and 08-11, which were before the rollout. None went out on Monday 08-18. The logs end 08-20, so later Mondays aren't covered.
- **Evening TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some cases are in triage status with `triage_at` NULL, which raises the TypeError. The per-case `try` catches it, so the job logs it and skips that case. I haven't confirmed which code path leaves `triage_at` unset. The reopen button handler is the likeliest, since it sets the status without running the flow that stamps the timestamp.
- **Fixes (uncommitted, not deployed):**
  - `_is_reminder_day()` is back to `isoweekday() == 1`, with a regression test that fails on the broken constant.
  - The close reminder counts from `created_at` when `triage_at` is missing, with a test that reproduces the TypeError without the fix.
  - Full suite: 370 passed, 4 skipped. Eight failures in the `ai`, `database`, and `entity` tests also fail on clean `main`, so they predate these changes.
- **Not yet done:** Missed Monday reminders from 08-18 onward aren't resent automatically. The fix also needs to be committed and deployed.

**Report fields**

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```