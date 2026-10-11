**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check. It moved the check `date.today().isoweekday() == 1` into a helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py:31`. The helper compares against `calendar.MONDAY` instead:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (I checked), because the `calendar` module numbers weekdays from 0. `isoweekday()` returns 1 to 7, with Monday as 1. The comparison is therefore never true, on any day. Both `case_close_reminder` (triage cases) and `case_stable_reminder` call the helper, so neither sends anything now. The daily triage reminder (`case_triage_reminder`) doesn't use it, which is why those kept arriving. No settings changed.

**Deploy that shipped it:** the image `registry.example.com/dispatch:main-81d8ae42`, started on 2025-08-13 at 16:40Z. The scheduler pod `scheduler-mhtsgqwwx-q5q2n` started then, and so did the web pod `web-5dkmr9s9s-xxktx`. Commit `81d8ae42` is the head of the range and includes `c509d45e`. The previous image was `main-b05613b5`, running since 2025-07-30. The deploy also carried `32fa810f` (the `stable_at` None guard) and other unrelated commits. The refactor is the only change that touches the Monday check.

**Evidence from the logs:**
- "Case close reminder sent" appears 4 times on Mon 07-28, 6 on Mon 08-04 and 5 on Mon 08-11, all before the deploy.
- It appears 0 times on Mon 08-18, after the deploy. The only "close reminder sent" line that day is the incident one, not the case one.
- After the deploy, `case_stable_reminder` and `case_close_reminder` finish in about 0.03 to 0.05 seconds with no sends, where before they took 1 to 2 seconds and sent messages.

**Fix to apply when you're ready:** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. I'd also add a test that mocks a Monday date.

**Separate, pre-existing issue:** `case_close_reminder` still logs a `TypeError` for triage cases whose `triage_at` is `None` (`datetime - None`). It was happening before the deploy as well, and it's caught per case so it doesn't stop the other cases. The stable reminder got a `stable_at` guard in `32fa810f`, but the triage one never did.

I haven't changed any code.

----- next turn -----

The Monday reminders are fixed. The new tests pass with the fix, and three of them fail on the buggy code. I haven't committed anything.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, which matches `calendar.MONDAY`, so the two conventions line up.

**Tests:** the new file is `tests/case/test_case_scheduled.py`, with 13 cases.
- **Weekday check:** `_is_reminder_day()` is checked for all seven days of the week of 2025-08-18, a Monday. It must be true only on Monday.
- **Task-level check:** both `case_close_reminder` (triage) and `case_stable_reminder` are run with a case that is 10 days old. They must send a reminder on Monday and must not on Sunday or Tuesday.
- **Without the fix:** with the fix stashed, the three Monday-sending cases fail: the weekday check and the two task-level checks. The no-send cases pass either way.

The task-level tests get the real task functions from `scheduler.registered_tasks` and unwrap the project decorator. They use mocks, so they don't touch PostgreSQL.

I didn't touch the separate issue I flagged earlier, where `case_close_reminder` still logs a `TypeError` for triage cases with no `triage_at`. It's caught per case, so it doesn't stop the other reminders. I can add the same kind of guard that the stable reminder has if you want.

----- next turn -----

The nightly `TypeError` is fixed. A triage case with no `triage_at` now counts its age from `created_at`, so it still gets the weekly reminder. All 15 tests in `tests/case/test_case_scheduled.py` pass. With the `src` changes stashed, 5 of them fail, including the two new ones. Nothing is committed.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at` for every triage case. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), which runs on a status transition. `service.create` takes `status` straight from the incoming case (`src/dispatch/case/service.py:205`). A case created already in `triage`, or one that predates the `triage_at` column, therefore never gets a value. The subtraction fails for those cases and the error is caught per case and logged. This is my reading of the code; I didn't query the database to confirm which cases are affected.

**Impact:** it was harmless to the other cases, but the affected ones could never get their weekly close reminder, even before the Monday bug.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now computes `datetime.utcnow() - (case.triage_at or case.created_at)`, with a comment explaining why.

**Tests:** I added a test to `tests/case/test_case_scheduled.py` for a triage case with `triage_at=None`. A case created 10 days ago on a Monday gets a reminder and logs no exception. A case created 3 days ago gets none.

----- next turn -----

**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`. The helper compares `date.today().isoweekday()`, which runs 1 to 7, against `calendar.MONDAY`, which is 0. The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent anything. The daily triage reminder doesn't use the helper, which is why it kept working.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13 at 16:40Z on the scheduler and web pods. It replaced `main-b05613b5`, which had been running since 2025-07-30.
- **Evidence:** "Case close reminder sent" appears 4 times on 07-28, 6 on 08-04 and 5 on 08-11. It appears 0 times on 08-18, and the jobs finish in about 0.03 to 0.05 seconds with no sends.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Regression tests are in `tests/case/test_case_scheduled.py`, and three of them fail on the old code.
- **Second issue (the evening `TypeError`):** `case_close_reminder` computed `utcnow() - case.triage_at`. `triage_at` is only set by the triage transition flow, so cases created directly in triage status, or created before the column existed, have none. Those cases logged an error every evening and could never get a reminder. The job now falls back to `created_at`, with a test.
- **Not committed:** all the changes are in the working tree.

The 2025-08-11 reminders were sent. The 2025-08-13 deploy was the first to ship the bug, so 2025-08-18 was the first Monday that went unsent.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at