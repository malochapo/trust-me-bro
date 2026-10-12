The weekly reminders stopped because of a Monday check that can never be true. It shipped in image `main-81d8ae42`, which was rolled out on 2025-08-13 at 16:40Z.

**Root cause**

- Commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), replaced two inline checks with a shared helper. The inline check was `date.today().isoweekday() == 1`.
- The helper is `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31`. It returns `date.today().isoweekday() == calendar.MONDAY`.
- The two numbering schemes differ. `isoweekday()` runs Monday=1 to Sunday=7, but `calendar.MONDAY` is 0 (I confirmed this). The comparison is therefore never true.
- `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both gate on this helper, so both went silent.
- The daily `case_triage_reminder` doesn't use it, which is why those still arrive.
- The commit was presented as a pure refactor, so nobody expected a behaviour change.

**The deploy**

- Both the scheduler and web pods were running `registry.example.com/dispatch:main-b05613b5` (a build from 2025-07-29) from 2025-07-30 17:10Z. That build predates the refactor.
- Both were replaced on 2025-08-13 at 16:40Z with `main-81d8ae42`, "fix(case): exclude resolved_by in update (#6183)" from 2025-08-12. It is the first image that contains `c509d45e`, and it also carried about 25 other commits.
- The scheduler log shows reminders going out on Monday 07-28, 08-04 and 08-11 (5, 7 and 6 case reminder lines). On Monday 08-18, the first Monday after the deploy, `case_close_reminder` and `case_stable_reminder` sent nothing. The only case reminder that day was the daily triage one.
- Only these two images appear in the logs. The "since mid-August" timing fits the 08-13 rollout.

**A separate error in the logs**

On 08-18, `case_close_reminder` logged `unsupported operand type(s) for -: 'datetime' and 'NoneType'` at `scheduled.py:47`. That is `datetime.utcnow() - case.triage_at`, so some triage case has no `triage_at`. It is caught per case and doesn't stop the loop, so it isn't why the reminders stopped. It does mean that case's reminder would be skipped once the Monday check is fixed. The same error appeared daily in July in `case_stable_reminder`, which the `stable_at` guard in `32fa810f` fixed. `case_close_reminder` has no equivalent guard.

**Suggested fix (not applied)**

Compare against `calendar.MONDAY` using `date.today().weekday()`, or use `isoweekday() == 1`. A small test that mocks the date for a Monday and a Tuesday would have caught this. Consider adding the same `None` guard to `triage_at`.

I haven't changed any code.

----- next turn -----

I saved the investigation to the sobre session, so tomorrow's session can start with `sobre_session` `action="load"`. I saved one task, three findings and one decision.

- **Task:** the reminder outage investigation. The root cause is found and no code has been changed.
- **Root cause:** commit `c509d45e` added `_is_reminder_day()` at `src/dispatch/case/scheduled.py:31`. It compares `isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The check is never true, so the weekly close and stable reminders never send.
- **Deploy:** image `main-81d8ae42` went to production on 2025-08-13 at 16:40Z. The previous image, `main-b05613b5`, predates the refactor. Reminders went out on the Mondays of 07-28, 08-04 and 08-11, and none went out on 08-18.
- **Separate issue:** `case_close_reminder` has no `None` guard on `triage_at`. This is not what caused the outage.
- **Decision:** the proposed fix is not applied. It changes the weekday comparison, adds a Monday and Tuesday test, and adds the `triage_at` guard.

I didn't write anything to the file-based memory. The session record is enough for this investigation, and the fix and deploy details are already in the git history and the logs.

----- next turn -----

Assignees stopped getting the weekly Monday reminders because `_is_reminder_day()` could never be true. I fixed it, and the new test passes with the fix and fails without it.

**Cause:** commit c509d45e (2025-08-12) moved the Monday check into `_is_reminder_day()`. It kept `date.today().isoweekday()`, which counts Monday as 1, but compared it to `calendar.MONDAY`, which is 0. The check was therefore false on every day, and `case_close_reminder` and `case_stable_reminder` never sent anything.

**Fix:** in `src/dispatch/case/scheduled.py`, the check now uses `date.today().weekday() == calendar.MONDAY`.

**Evidence from the scheduler log:**
- "Case close reminder sent" appears on the Mondays 2025-07-28, 08-04 and 08-11, and never after that.
- The scheduler pod restarted on image `main-81d8ae42` on 2025-08-13, and that image contains c509d45e.
- The previous image, `main-b05613b5`, does not contain it.
- The first Monday after the deploy was 2025-08-18.

**Test:** `tests/case/test_case_scheduled.py` has 9 tests. It checks that `_is_reminder_day()` is true only on Monday. It also runs the registered close and stable reminder tasks and checks they send on a Monday and not on a Tuesday. It uses mocks, so it needs no database. Without the fix, 3 of the 9 fail; the other 6 are the non-Monday cases, which pass either way.

I did not run the rest of the suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18