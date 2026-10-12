**Root cause:** the weekly Monday check in `src/dispatch/case/scheduled.py` never passes, so the weekly case close and stable reminders are never sent.

The helper added in `c509d45e` compares the day against `calendar.MONDAY`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # scheduled.py:31-33
```

`calendar.MONDAY` is `0`, because Python's `calendar` module counts Monday as 0. `isoweekday()` counts Monday as 1. The comparison is therefore always false, so `q >= 1 and _is_reminder_day()` is never true. The code before the refactor compared against the literal `1`, which was correct. The daily triage reminder doesn't use this check, which is why it still arrives. (I couldn't run Python to confirm the constant; the value comes from the standard library's documented behaviour.)

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. Kubelet shows the `scheduler` and `web` containers starting on it at **2025-08-13T16:40Z**. `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) is an ancestor of `81d8ae42`, and the previous deploy (`main-b05613b5`, 2025-07-30) doesn't include it.

**Confirmation in the logs:**
- Monday 2025-08-11 (before the deploy): 5 case close reminders sent.
- Monday 2025-08-18 (first Monday after the deploy): 0 case close reminders, 1 incident close reminder, 1 triage reminder.

**Secondary finding, not the cause:** from 2025-07-28 to 2025-08-12 the stable reminder logged a `TypeError` (`datetime - NoneType`) on every daily run, because some stable cases have no `stable_at`. `32fa810f` ("not all cases have a stable_at date") added the guard, and the errors stop after the 08-13 deploy. That fix is already in the `main-81d8ae42` image, so it doesn't explain the missing reminders.

**Suggested fix (not applied, per your instruction):** compare against `1` or use `date.today().weekday() == calendar.MONDAY`. A test that pins a known Monday date would have caught this.

----- next turn -----

The weekly Monday reminders work again, and there is a regression test for the bug. I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides of the comparison are now 0-based, so Monday matches.

**Regression test** (new file `tests/case/test_case_scheduled.py`): a parametrized test patches `date` in the scheduled module and checks `_is_reminder_day()` for Monday 2025-08-18 through Sunday 2025-08-24. It fails on the buggy line (the Monday case) and passes with the fix. I checked both directions by temporarily restoring the buggy line.

**Test results** (`python -m pytest`):
- `tests/case`: 22 passed.
- Full suite: 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed the fix and reran them, and the same 8 fail on the original code, so they predate this change and are unrelated to it. I didn't investigate them.

**Not done:** I didn't deploy or verify against production. The next Monday run (2025-08-25 in the logs' timeline, or the next real Monday) is the first real check.

----- next turn -----

The close reminder TypeError is fixed. Cases without `triage_at` now count from `created_at`, and there's a regression test for it.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. `triage_at` is only set in `case_triage_status_flow` (`flows.py:592`), but the Slack handlers set `case.status = CaseStatus.triage` directly (`plugins/dispatch_slack/case/interactive.py` around lines 1312, 1427 and 2246). Cases moved to triage that way never get a `triage_at`, so the subtraction raises. The per-case `except` logs it and moves on, so those cases never get the reminder. The errors appear every evening from 2025-07-28 onward.

**Fix** (`src/dispatch/case/scheduled.py:47-49`): the job now uses `triage_start = case.triage_at or case.created_at`. Cases that already have `triage_at` count from it, as before.

**Tests** (`tests/case/test_case_scheduled.py`, now 10 tests):
- A triage case with no `triage_at` and created 8 days ago gets a reminder.
- A case with no `triage_at` created 2 days ago does not.
- When both timestamps exist, `triage_at` takes precedence.

The tests call the job through `scheduler.registered_tasks`, since the decorators return `None`. I confirmed the fallback test fails on the old line and passes with the fix.

**Results** (`python -m pytest`): `tests/case` passes (22 tests, including the new ones). The full suite has 369 passed, 4 skipped and the same 8 failures as before (`ai`, `database`, `entity`), which fail on the original code too.

**Not changed:**
- The Slack paths still set `triage` without `triage_at`. The fallback covers the reminder, but other code that reads `triage_at` may still see `None` for those cases. Fixing the Slack handlers to go through the flow would be a separate change.
- `case_stable_reminder` still skips cases without `stable_at`. You asked about the close reminder only, so I left it alone. Say if you want the same `created_at` fallback there.

----- next turn -----

**Recap**

- **Missing weekly reminders:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check never passed. Weekly case close and stable reminders stopped. Daily triage reminders were unaffected. The bug came in with `c509d45e` on 2025-08-12 and reached production in the `main-81d8ae42` deploy, which started on the scheduler and web pods on 2025-08-13 at 16:40Z. The Monday 2025-08-11 run sent 5 case close reminders; Monday 2025-08-18 sent none.
- **Fix:** `date.today().weekday() == calendar.MONDAY`. A parametrized test covers Monday through Sunday; it fails on the old line and passes with the fix.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Slack handlers set `status = triage` directly, bypassing `case_triage_status_flow`, so those cases have no `triage_at`. The job now uses `case.triage_at or case.created_at`. Three tests cover the fallback, the recent-case skip, and `triage_at` precedence; the fallback test fails on the old line.
- **Tests:** `tests/case` passes (22). The full suite has 369 passed and 4 skipped, plus 8 failures in `ai`, `database`, and `entity` that also fail without these changes.
- **Not done:** Nothing is committed. The Slack handlers still skip `triage_at`, and `case_stable_reminder` still skips cases without `stable_at`. Both are outside what you asked for.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at