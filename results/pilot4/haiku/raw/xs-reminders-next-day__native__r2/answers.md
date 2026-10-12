**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check from a literal to `calendar.MONDAY`. That constant is `0`, because Python's `calendar` numbers Monday as 0. `date.isoweekday()` returns 1 for Monday, so the check is now `isoweekday() == 0` and never matches.

In `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # 1 == 0 -> always False
```

Before the refactor, the code compared against `1`, which was correct. The helper is used by `case_close_reminder` (line 49) and `case_stable_reminder` (line 95), so both weekly reminders are suppressed. `case_triage_reminder` doesn't call the helper, so the daily triage reminders keep working.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. The scheduler started on it at 2025-08-13T16:40:06Z, and the web pod at 16:40:07Z. `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", and it contains `c509d45e` (`git merge-base --is-ancestor` confirms this). The previous scheduler image, `main-b05613b5` from 2025-07-30, does not contain the commit.

**Log evidence:**
- Monday 2025-08-11, still on the old image: "Case close reminder sent" lines appear for several assignees.
- Monday 2025-08-18, on the new image: no case close or stable reminders are sent. The triage reminder and incident close reminder still run.

I'm inferring from the image tag name that `main-81d8ae42` is the build of that commit. The ancestry check and the timing match, but I haven't checked the deploy record itself.

**Unrelated noise in the logs:** `case_close_reminder` (line 47) and, from 07-28, `case_stable_reminder` raise `TypeError` for cases whose `triage_at` or `stable_at` is NULL. The per-case try/except absorbs these, so they don't stop other cases, but they spam the logs. `case_stable_reminder` has a `stable_at` guard since `32fa810f`, and `case_close_reminder` has no equivalent guard.

No code has been changed. The likely fix is `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based like `calendar`), or `isoweekday() == 1`. A test that pins `_is_reminder_day` to a Monday date would have caught this.

----- next turn -----

The weekly Monday reminders were never sent because a weekday check compared against the wrong number. The fix is in and a regression test covers it. Nothing is committed.

**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). Monday never matched, so `case_close_reminder` and `case_stable_reminder` skipped every Monday. Commit `c509d45e` (a refactor that moved the check into this helper) introduced it. The original code used `isoweekday() == 1`, which was correct.

**Evidence from the logs:**
- The last close/stable reminders were sent on Monday 2025-08-11, before the refactor's deploy.
- The first deploy containing `c509d45e` was `main-81d8ae42`, which started on 2025-08-13.
- On Monday 2025-08-18 there are no case close or stable reminder entries. The incident close reminder, which uses the correct `isoweekday() == 1`, still ran that day.

**Changes:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar.MONDAY`, so the two agree.
- `tests/case/test_case_scheduled.py` (new): a parametrized test patches `date` in the module and checks that `_is_reminder_day()` is true on Monday and false on Tuesday through Sunday. Against the original code it fails on Monday, and it passes with the fix.

**Verification:** `python -m pytest tests/case` passes (22 tests, including the 7 new cases). I did not run the full suite.

**Not addressed:** the scheduler logs an error every day for `case_close_reminder`, because `case.triage_at` is `None` for some cases. The per-case try/except keeps this from blocking other cases, but it is noisy and worth a follow-up.

I did not have yesterday's findings in this conversation. I rebuilt the diagnosis from the logs and the repo.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18