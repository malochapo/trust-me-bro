## Recap

**Symptom:** Since mid-August, assignees no longer receive the Monday reminders for long-running triage and stable cases. The daily triage reminders still arrive, and nobody changed the settings.

**Root cause (weekday bug):** Commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with a helper that compares against `calendar.MONDAY`. `isoweekday()` is one-based (Monday = 1), while `calendar.MONDAY` is zero-based (Monday = 0). The helper therefore returned False every day, so no weekly reminder was sent. Both the triage close reminder and the stable close reminder call the helper, which is why both stopped. The daily triage reminder doesn't call it, so it kept working.

**Deploy:** Commit `c509d45e` is an ancestor of `81d8ae42`. The scheduler and web containers rolled out `main-81d8ae42` on 2025-08-13 at 16:40Z. On 2025-08-11, the last Monday before the deploy, close reminders were still sent. After the deploy, none were sent.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. The regression test `tests/case/test_case_scheduled.py::test_is_reminder_day` fails on the old check and passes on the fix.

**Secondary bug (evening TypeError):** Some triage cases have no `triage_at`. Several paths set a case to `triage` without running the transition flow that sets it: the reopen and triage Slack button handlers, and the `(_, CaseStatus.triage)` branch of the transition dispatcher. Subtracting `None` raised a TypeError, which the per-case `try` caught, so those cases were skipped. The fix counts from `created_at` when `triage_at` is missing, with tests for both cases. The 24 error lines in the logs don't include case IDs, so I couldn't confirm which path produced each one.

**Open items:**
- The root cause of the missing `triage_at` (the flow bypasses) is not fixed, only worked around.
- `FIRST_MISSED` is the first Monday after the deploy. The logs show no close reminders that day, but I can't confirm from the logs that there were eligible cases.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at