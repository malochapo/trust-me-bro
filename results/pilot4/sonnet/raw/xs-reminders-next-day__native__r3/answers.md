**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced the inline `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1–7, with Monday = 1. `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0. The comparison can therefore never be true. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) use the helper, so neither sends anything any more.

The daily triage reminder doesn't use the helper, which is why it still arrives. No settings changed, and the refactor was meant to be behaviour-neutral.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which is "fix(case): exclude resolved_by in update (#6183)", committed 2025-08-12 14:47 -0700.
- `git merge-base --is-ancestor` confirms `c509d45e` is in `81d8ae42`. The previous image, `main-b05613b5`, did not contain it.
- The kubelet "Started container" lines show the web and scheduler pods rolling to that image at **2025-08-13 ~16:40 UTC**. The scheduler pod went from `scheduler-xdp7k6gs2q-w6cj7` to `scheduler-mhtsgqwwx-q5q2n`.

**Evidence in the logs:** "Case close reminder sent to …" appears only on the Mondays before the deploy:

| Monday | Close reminders sent |
|---|---|
| 2025-07-28 | 4 |
| 2025-08-04 | 6 |
| 2025-08-11 | 5 |
| 2025-08-18 (first Monday after the deploy) | 0 |

On 08-18 the job ran with no errors from the helper and sent nothing. The daily triage reminder was sent on 08-18 as before.

**Unrelated noise:**
- Every run before the deploy logged `unsupported operand type(s) for -: 'datetime' and 'NoneType'` from `case_close_reminder` and `case_stable_reminder`. These come from cases with a null `triage_at` or `stable_at`. The errors are caught per case.
- Commit `32fa810f` guarded the `stable_at` case. The `case_close_reminder` error was still logged on 08-18 (line 47 of the new code), so a case with a null `triage_at` is still being skipped. That is a separate issue and not why the Monday reminders stopped.

**Suggested fix (not applied):** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. A small test that mocks the date for a Monday and a Tuesday would stop this recurring. Cases that sat in triage or stable since 08-18 and 08-25 missed their reminders, so you may want to send a catch-up after the fix ships.

----- next turn -----

Assignees stopped getting the Monday reminders because `_is_reminder_day()` compared the wrong numbering. The fix is in `src/dispatch/case/scheduled.py` and the new test passes.

**Cause:** `_is_reminder_day()` returned `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was true only on Sundays. The reminders run at 18:00 UTC and, in practice, never fired on a Monday.

**Origin:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the old inline `isoweekday() == 1` check into this helper. Both `case_close_reminder` (triage cases) and `case_stable_reminder` call it.

**Deploy and timing:** commit `c509d45e` is contained in commit `81d8ae42`. Both the scheduler and the web containers started on image `main-81d8ae42` on 2025-08-13 at 16:40Z. The scheduler log shows close reminders sent on Mondays 07-28, 08-04 and 08-11. There are none on 08-18, and the log ends on 08-20. I couldn't check the earlier image `main-b05613b5`: that commit isn't in this repo, so I'm inferring it predates the refactor from the date.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` covers the helper on a Monday, Tuesday and Sunday. It also runs both reminder tasks with a case 10 days old and checks that a reminder is sent on a Monday but not on a Tuesday. All 5 tests pass with the fix. With the fix stashed, 3 of them fail (the Monday helper check and both task checks).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18