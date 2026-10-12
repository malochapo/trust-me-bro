I'm stopping here because the budget is nearly used up: $0.001 of $3 remains. The root cause and the deploy are not confirmed yet, so this is a partial result.

**What the scheduler log shows so far**

- `case_stable_reminder` (`dispatch/case/scheduled.py`) failed every day at 18:00 UTC from 2025-07-28 through 2025-08-12. Each failure was `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` at line 101. The traceback points to line 93, `span = datetime.utcnow() - case.stable_at`, so the job was reading `case.stable_at` when it was `None`.
- From 2025-08-13 onward the `ERROR` lines stop, but the job still logs a `DEBUG` completion line each day through 2025-08-20. That fits a change that stopped the crash, possibly by skipping cases with no `stable_at`, but that is not confirmed. The fact that the error stopped on 08-13 is the lead to follow for the deploy.
- The weekly incident report job logs `No AI plugin enabled` on Mondays. That is a separate job and is not the weekly case reminder.

**What is not yet established**

- I have not checked `api.log`, so I have not found which deploy changed how `stable_at` is set or cleared. That is the thing to look for next.
- I have not read the reminder code in the repo, so I cannot say whether the weekly reminder shares this query or is a separate path that also fails.
- I have not confirmed that the weekly reminder is actually the job that stopped sending. The log shows a daily job failing, and I have not matched it to the Monday reminders.
- I did not record findings with `sobre_session`, and I did not load earlier session notes. Those were skipped because of the budget.
- I made no code changes, as you asked.

**Next steps if you want to continue**

1. Grep `api.log` for `stable_at` and for deploy or version markers between 2025-08-12 and 2025-08-13. Look for the code change that began setting or clearing `stable_at`.
2. Read `dispatch/case/scheduled.py` around lines 80–110 and find the weekly reminder path.
3. Raise the budget if you want me to finish this.

----- next turn -----

The weekly Monday reminders were skipped because of an off-by-one in the weekday check, and that is now fixed with a regression test.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0). It was never true, so the close reminders for triage and stable cases were never sent. The check came from commit `c509d45e`, a refactor that moved the old inline `isoweekday() == 1` into this helper.

**Fix:** `src/dispatch/case/scheduled.py:33` now uses `date.today().weekday() == calendar.MONDAY`, which is consistent with the constant.

**Regression test:** `tests/case/test_case_scheduled.py` runs `_is_reminder_day()` for each day of a week with the date patched. Monday must return True and the other six days False. With the old code the Monday case fails and the other six pass; with the fix all seven pass. `python -m pytest tests/case` passes (22 tests).

**What the logs show:**
- The scheduler and API were redeployed as `main-81d8ae42` on 2025-08-13 at 16:40. That image contains `c509d45e`.
- Monday 2025-08-11 was before that deploy, so its reminders were fine.
- Monday 2025-08-18 is the first Monday with no close-reminder sends. The 18:00 run logs only the triage reminders and the error entries for cases with no `triage_at`.

I haven't committed the change. Nothing else in the logs points to a second cause for this symptom. The `NoneType` errors for `triage_at` on the close-reminder path are a separate issue, and I left them alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18