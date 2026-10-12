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