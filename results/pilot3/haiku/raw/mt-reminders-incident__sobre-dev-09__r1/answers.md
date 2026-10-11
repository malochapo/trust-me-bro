The root cause is a Python constant mismatch introduced in `c509d45e`. It was deployed to production in the scheduler on Aug 13 as part of image `main-81d8ae42`. I haven't changed any code.

**Root cause**

`c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, Aug 12) moved the Monday test into a helper in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Monday is 0 in the `calendar` module). I confirmed both values in the sandbox: `calendar.MONDAY = 0`, `isoweekday()` of 2025-08-11 is `1`. So `_is_reminder_day()` is always False, and `case_close_reminder` and `case_stable_reminder` never send. The code it replaced compared against the literal `1`, which was correct.

The daily triage reminder (`case_triage_reminder`) doesn't call this helper, which is why it still arrives.

**Deploy that shipped it**

- The scheduler pod was started on `2025-08-13T16:40:06Z` with image `registry.example.com/dispatch:main-81d8ae42` (`scheduler.log:18851`). The web pod got the same image at 16:40:07Z (`api.log:13201`).
- `81d8ae42` is the tip of `main` at that point and contains `c509d45e` (verified with `git merge-base --is-ancestor`).
- Before that, the scheduler ran `main-b05613b5` from 2025-07-30, which still had the literal `== 1` check.

**Evidence in the logs**

- Monday 2025-08-04 (old image): 6 "Case close reminder sent" lines.
- Monday 2025-08-11 (old image, before the Aug 13 deploy): 5 close reminders sent.
- Monday 2025-08-18 (new image): no close reminders, and no stable reminders for any day. Only triage reminders and incident reminders were sent.
- Across the whole window, "Case close reminder sent" appears only on 07-28, 08-04 and 08-11.

**Fix (not applied)**

Compare against 1, or use `calendar.MONDAY`'s equivalent, e.g. `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar.MONDAY`, and `isoweekday()` is 1-based. Then add a test for `_is_reminder_day()` on a Monday, since nothing currently exercises it.

**Separate issue I noticed**

`case_stable_reminder` was also crashing daily from 2025-07-28 on cases with `stable_at = None`. That was fixed by `32fa810f` on Aug 11 (the `if case.stable_at:` guard). `case_close_reminder` still has the same unguarded `datetime.utcnow() - case.triage_at` (`src/dispatch/case/scheduled.py:47` at HEAD). Its per-case `try/except` keeps the other cases going, but it logs an error for each triage case with no `triage_at` every day. It doesn't cause the missing Monday reminders, but a guard would stop the noise.

----- next turn -----

The weekly Monday reminders are fixed, and a regression test covers the bug. I haven't committed anything.

**The fix**

In `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday()` instead of `isoweekday()`. `calendar.MONDAY` is 0, and `weekday()` is 0-based like it, so the comparison works. The old `isoweekday()` is 1-based, so the check was never true.

**The regression test**

`tests/case/test_case_scheduled.py` pins `date.today()` to each day of one week and checks that `_is_reminder_day()` is True only on Monday. It fails on the old code for Monday (`assert False is True`), which is the case that was broken. The other six days pass with the bug too, since it never returned True.

**Test results**

- `python -m pytest tests/case`: 22 passed, including the new test.
- Full `python -m pytest`: 366 passed, 4 skipped, 8 failed. All 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. I stashed my change and ran those three files: the same 8 fail without it, so they predate this fix. I didn't investigate them.

**Not addressed**

`case_close_reminder` still does `datetime.utcnow() - case.triage_at` with no None guard. Cases without a `triage_at` log an error every day. The per-case `try/except` keeps the other cases going, so this doesn't affect the reminders, but I left it alone because you asked for only the Monday fix.

----- next turn -----

The job now counts from `created_at` when `triage_at` is missing, and the tests cover it. Nothing is committed.

**Cause of the TypeError**

`triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Some paths move a case into triage without running that flow, so the column stays NULL. `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427` is one of them: it assigns `case.status = CaseStatus.triage` directly. The job then does `datetime.utcnow() - None`, raises the TypeError, and the per-case `try/except` logs it and skips that case. I confirmed the reopen path from the code; I didn't check every path that can produce a NULL `triage_at`, and I can't see which production cases are affected.

**The fix**

In `src/dispatch/case/scheduled.py`, `case_close_reminder` now uses `datetime.utcnow() - (case.triage_at or case.created_at)`, with a comment explaining the fallback. `created_at` is non-null on every case, so the fallback can't fail.

**Tests**

`tests/case/test_case_scheduled.py` now has three tests that run the job's undecorated body on a Monday:
- `triage_at` is missing and the case was created 8 days ago: a reminder is sent. This fails on the old code and passes with the fix.
- `triage_at` is missing and the case was created 2 days ago: no reminder.
- `triage_at` is set and 8 days old, with `created_at` 30 days old: the reminder is sent from `triage_at`, so the fallback doesn't override it.

Two things I found while writing them:
- `scheduler.add` returns `None`, so the job is looked up in `scheduler.registered_tasks` by name.
- `CaseFactory` declares `status` under `class Params`, so `status=` passed to the factory never reaches the model. The tests set `case.status` after creation.

**Results**

- `python -m pytest tests/case`: 25 passed.
- Full `python -m pytest`: 369 passed, 4 skipped, 8 failed. The 8 failures are the same ones as before (AI service, database and entity tests), and they also fail without my change.

----- next turn -----

Recap for the incident report:

**Symptom.** Since mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. Daily triage reminders kept arriving, and nobody changed the reminder settings.

**Root cause.** Commit `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") moved the Monday test into `_is_reminder_day()`, which compared `date.today().isoweekday()` (1 for Monday) with `calendar.MONDAY` (0 in Python). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent. The daily triage reminder doesn't use this check, so it kept working. The fix changes the call to `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. A regression test in `tests/case/test_case_scheduled.py` pins each weekday and fails on the old code for Monday.

**Deploy.** The scheduler restarted on 2025-08-13 at 16:40 UTC with image `main-81d8ae42`, which is `main` at that point and contains `c509d45e`. The web pod got the same image. The previous scheduler image, `main-b05613b5`, still sent reminders on Monday 2025-08-11.

**Impact.** The first missed Monday was 2025-08-18. The logs show no close or stable reminders that day, and none since.

**Evening TypeError.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some cases reach triage without `triage_at` being set. `triage_at` is only set in `case_triage_status_flow`, and the Slack reopen handler (`reopen_button_click`) assigns `CaseStatus.triage` directly without running that flow. The job logged the TypeError for each such case and skipped it, so those cases never got a weekly reminder. The fix counts from `created_at` when `triage_at` is missing. Three tests cover the fallback, a recent case that should not be reminded, and the case where `triage_at` is set. I haven't confirmed which production cases lack `triage_at`.

**Separate issue.** `case_stable_reminder` was also failing daily from 2025-07-28 on cases with no `stable_at`. Commit `32fa810f` (Aug 11) added the guard.

**Status.** Both fixes are uncommitted in the working tree. The full suite has 8 failures in the AI, database and entity tests. They also fail without these changes.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```