**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check to compare against `calendar.MONDAY`. In Python that constant is `0`, while `date.today().isoweekday()` returns `1` for Monday. So `_is_reminder_day()` is never true, and the weekly close reminders for triage and stable cases never fire.

The buggy line is in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # calendar.MONDAY == 0
```

The original code compared `isoweekday() == 1`, which was correct. The refactor broke it. Both `case_close_reminder` and `case_stable_reminder` call `_is_reminder_day()`, which is why both weekly reminders stopped. The daily triage reminder (`case_triage_reminder`) doesn't use this check, so it still sends.

**Deploy that shipped it:** the API log shows `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13 at 16:40Z. Commit `81d8ae42` is the HEAD of that build, and `c509d45e` is an ancestor of it. The earlier build, `main-b05613b5`, does not contain the refactor. The scheduler's image isn't logged, so I'm inferring it was deployed alongside the API.

**Log evidence:**
- Monday 2025-08-04 (before the refactor): 5+ `Case close reminder sent` lines, and the stable path also sent reminders.
- Monday 2025-08-11 (before the deploy): 5 `Case close reminder sent` lines.
- Monday 2025-08-18 (first Monday after the deploy): 0 case close reminder sends. Triage and incident reminders still went out.

**Side effect of the same deploy:** `32fa810f` ("fix(scheduler): not all cases have a stable_at date") was in that build too. It guards `case_stable_reminder` with `if case.stable_at:`. That removed the daily `datetime - NoneType` errors that had run from 07-28 through 08-12. The disappearance of those errors may look like a fix, but the weekly sends are still blocked.

**Not changed:** no code was edited. A likely fix is to restore `isoweekday() == 1` (or make `_is_reminder_day()` compare against `calendar.MONDAY + 1`). Tests should cover the weekday check, since nothing caught this.

**Separate issue spotted:** `case_close_reminder` logs the same `datetime - NoneType` error at `scheduled.py:51`, on `case.triage_at` being None. The per-case try/except contains it, so it only skips the affected case, but it is worth fixing too.

----- next turn -----

The weekly reminders are fixed, and a regression test covers the bug. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` compared `date.today().isoweekday()` against `calendar.MONDAY`, which is `0`, so it never matched. It now compares against `1`, the `isoweekday()` value for Monday. I removed the unused `calendar` import and added a comment saying why the constant isn't used.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `date` in the scheduled module and checks `_is_reminder_day()` for every day of the week from Monday 2025-08-11 through Sunday 2025-08-17.
- Against the old code, the Monday case fails and the other six pass.
- With the fix, all seven pass.

**Test results:** `python -m pytest tests/case` passes, 22 tests. I didn't run the full suite.

**Not changed:** `case_close_reminder` still logs the `datetime - NoneType` error when `triage_at` is None, from my earlier report. The per-case try/except contains it, so only the affected case is skipped. I left it alone since you asked for the weekly-reminder fix only.

----- next turn -----

The close reminder now falls back to the case's creation time when `triage_at` is missing, so those cases get their weekly reminder. I haven't committed anything.

**Cause:** the TypeError is `datetime - NoneType`. The job subtracts `case.triage_at`, and that is NULL for cases that reached triage without the triage flow running. The flow is the only place that sets `triage_at` (`src/dispatch/case/flows.py:594`). Three Slack handlers in `src/dispatch/plugins/dispatch_slack/case/interactive.py` (around lines 1312, 1427 and 2246) assign `case.status = CaseStatus.triage` directly and never call it. Each such case hits the error every evening. The per-case `try/except` catches it, so only that case is skipped, and it never gets a reminder.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the job now counts from `case.triage_at or case.created_at`. The comment explains why `triage_at` can be missing.

**Tests** (`tests/case/test_case_scheduled.py`, now 9 tests in total):
- A triage case with `triage_at=None` and created 8 days ago gets the reminder.
- A triage case with `triage_at=None` created 3 days ago gets none.
- The job is run through the scheduler's registered task, with the day check and the send function patched.
- With the fallback removed, the 8-day case test fails. With the fix, it passes.
- `python -m pytest tests/case` passes, 24 tests.

**Not changed:**
- The Slack handlers still skip the triage flow, so `triage_at` stays NULL for those cases. Setting it there, or calling the triage flow, would fix the root cause. I didn't change them since you asked for the reminder fallback only.
- `case_stable_reminder` still skips cases with no `stable_at` entirely, because of the guard added in `32fa810f`. Those cases get no weekly stable reminder. Applying the same created-at fallback there would be a small change if you want it.

----- next turn -----

**Recap**

- **Symptom:** assignees stopped getting the Monday reminders for long-running triage and stable cases from mid-August. Daily triage reminders kept going, and no reminder settings changed.
- **Root cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday test into `_is_reminder_day()`. That function compared `date.today().isoweekday()` against `calendar.MONDAY`, which is `0`, while `isoweekday()` returns `1` for Monday. The check was never true, so neither the close nor the stable reminders went out on Mondays.
- **Deploy:** the API log shows `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13 at 16:40Z. That build contains `c509d45e`. The scheduler's image isn't in the logs, so I'm inferring it was deployed with the API.
- **Evidence:** Monday 2025-08-11, before the deploy, still sent 5 case close reminders. Monday 2025-08-18, the first Monday after the deploy, sent none.
- **Fix:** `_is_reminder_day()` now compares against `1`. A regression test checks every weekday, and it fails on the old code.
- **Second issue:** the evening TypeError is in `case_close_reminder`. Cases moved to triage from the Slack handlers never get `triage_at` set, so the job's subtraction fails for them. The job now falls back to `created_at`, with a test. The Slack handlers themselves still skip the triage flow and were not changed.
- **Side effect of the same deploy:** `32fa810f` guarded the stable reminder against a missing `stable_at`. That stopped its daily error, but cases without `stable_at` still get no stable reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at