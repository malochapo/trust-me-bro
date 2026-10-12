**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check.

It replaced `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py:31-33`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. So `_is_reminder_day()` is never true. That also means it would be true on no day at all, since `isoweekday()` never returns 0. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) use the helper, so both weekly reminders stopped silently. The daily triage reminder (`case_triage_reminder`) doesn't use it, which is why it kept arriving. The refactor was described as behaviour-neutral, and no exception is raised, so nothing showed up in the logs.

**Deploy:** it reached production on 2025-08-13 at about 16:40 UTC. The scheduler and API pods were replaced at that time, and the new scheduler pod started on image `dispatch:main-81d8ae42`. The previous image was `main-b05613b5`. The new image's commit, `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)", 2025-08-12), sits after `c509d45e` on main. That makes it the first production build to include the helper, along with about 25 other commits made since `b05613b5`. The traceback line numbers in the logs confirm this. The new pod's `case_close_reminder` fails at line 47, matching `c509d45e`. The old pods' line 43 matches the earlier code.

**Log evidence:**

| Monday | Pod / image | "Case close reminder sent" lines |
|---|---|---|
| 07-28 | old | 5 |
| 08-04 | old | 7 |
| 08-11 | old (`b05613b5`) | 6 |
| 08-18 | new (`81d8ae42`) | 1 |

For 08-18, the one line is for an incident, not a case. The `scheduler.log` shows no case close reminders at all after the deploy. Cases with a null `triage_at` also still log a `TypeError` on the new pod, but this is a separate, older problem.

**Fix (not applied, per your instruction):** use `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`. A small test for `_is_reminder_day` would stop this recurring.

Assignees missed the 08-18 reminder and probably the 08-25 and 09-01 ones too. Any fix will only resume the reminders from the next Monday after it ships.

----- next turn -----

I saved what we found and decided in the sobre session. Tomorrow, start with `sobre_session` `action="load"` to bring it back.

The saved finding has the root cause, the deploy and the evidence. It also records the separate, older null `triage_at` error. The decision notes that no code has changed yet and lists the next step. That step is to fix the Monday check, add a unit test, and optionally guard against a null `triage_at`.

----- next turn -----

Weekly reminders were never sent after the 2025-08-13 deploy because the Monday check could never be true. I fixed it and added a regression test.

**Cause:** commit c509d45e ("share the weekly reminder check") moved the inline `date.today().isoweekday() == 1` into a shared helper. The helper compares `isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0). So `_is_reminder_day()` always returned False on Mondays, and both `case_close_reminder` (triage) and `case_stable_reminder` skipped every week.

**Evidence from the logs:**
- Close reminders were sent on 07-28, 08-04 and 08-11.
- On 08-18 only the triage reminder went out.
- The 08-13 deploy, image `main-81d8ae42`, contains c509d45e.

**Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now uses `weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` has 13 cases. They check that the helper is true only on Monday, and that both tasks send a reminder on Monday and none on other days. The tests pass with the fix. With the fix stashed, the three Monday cases fail.

**Unrelated errors in the logs:** the scheduler also logs a caught `datetime - None` error every day from `case_close_reminder` and `case_stable_reminder`. I didn't touch it; it comes from some cases having no `triage_at`, and the code at the log's line numbers (47 and 93) matches the current file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18