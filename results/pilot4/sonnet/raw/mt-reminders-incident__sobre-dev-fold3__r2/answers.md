**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). It broke the Monday check in the case reminders.

The refactor replaced the inline `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I checked). The helper can therefore never be true on a Monday. It is true on Tuesdays, where `isoweekday()` is 2 and ... actually Tuesday is `calendar.TUESDAY == 1`, so the helper is true on Tuesdays.

Both `case_close_reminder` (triage cases) and `case_stable_reminder` call the helper. Their reminders now only fire on Tuesdays, which the logs say is not what happens either (see below). The daily triage reminder doesn't use the helper, which is why it kept working.

**Deploy:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to production on 2025-08-13 at about 16:40Z. The scheduler container started at 16:40:06 and the web container at 16:40:07.
- `81d8ae42` ("fix(case): exclude resolved_by in update") contains the buggy helper. I confirmed `_is_reminder_day` is present at that commit.
- The previous image, `main-b05613b5`, was deployed on 2025-07-30 and doesn't have the helper.
- `c509d45e` itself was merged on 2025-08-12, before the deploy.

**Evidence from the scheduler log:** the reminders run daily at 18:00Z.
- Before the deploy, "Case close reminder sent" lines appear on Mondays 07-28 (5), 08-04 (7) and 08-11 (6).
- After the deploy, Monday 08-18 has no case close or stable reminders. The only case-reminder activity that day is the TypeError below.
- Tuesday 08-19 also has no sends, so the Tuesday behaviour I predicted from the code is not visible in the logs. I haven't explained why.
- There were also sends on 08-05 and 08-06, a Tuesday and a Wednesday, before the deploy. I didn't investigate those.
- The "Case triage reminder sent" lines continue every day, matching the daily triage reminders that still arrive.

**Separate pre-existing bug, not the cause:** `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` is logged at 18:00 on 16 days for `case_stable_reminder` and 16 for `case_close_reminder`, starting 2025-07-28. A case with no `stable_at` or `triage_at` aborts the whole project loop. Commit `32fa810f` ("not all cases have a stable_at date") is in the deployed range. The `main-81d8ae42` traceback still points at `case_close_reminder` (line 43/47), so the `triage_at` subtraction is still unguarded. This can silently drop reminders for other cases, so it is worth fixing alongside the weekday bug.

**Suggested fix when you want it:** compare against 1, or use `date.today().weekday() == calendar.MONDAY`. Also guard the `None` timestamps per case, so one bad case can't abort the loop. I haven't changed any code.

----- next turn -----

I've fixed the bug and added a regression test. Both are uncommitted.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides now use 0 for Monday.
- **Test:** `tests/case/test_case_scheduled.py` checks the helper on a Monday (true) and on a Tuesday, Wednesday and Sunday (false). All 4 cases pass with the fix. With the fix stashed, the Monday case fails, so the test would have caught the bug. I only ran this new test file, not the whole suite.

**Correction to my earlier write-up:** I said the buggy helper would fire on Tuesdays. That was wrong. `isoweekday()` returns 1 to 7 and `calendar.MONDAY` is 0, so the old comparison could never be true on any day. The reminders were off entirely after the deploy, which matches the logs (no sends on 08-18 or 08-19). I also said a case with a missing timestamp aborts the project loop. It doesn't, because each case is wrapped in its own `try/except`. Instead, it logs a `TypeError` for that case and moves on.

**Not changed:** `case_close_reminder` still subtracts `case.triage_at` without a `None` check, which is what produces those logged errors. It is a separate issue from the missing reminders. I can add the guard if you want.

----- next turn -----

The close reminder now counts from `created_at` when a case has no `triage_at`, and a new test covers it. The fix is uncommitted, like the Monday fix.

**What causes the TypeError:** `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`), which runs on the New→Triage and Closed→Triage transitions. A case that reaches the `triage` status any other way never gets the timestamp. I inferred that from the code and didn't find the specific cases in the data. The paths that lead there are creation directly in triage and any other status→triage change. `case_close_reminder` then computes `datetime.utcnow() - case.triage_at`, which raises on `None`. The per-case `try/except` logs the error and moves on, so these cases never get a reminder.

**The fix:** in `src/dispatch/case/scheduled.py`, the span is now `datetime.utcnow() - (case.triage_at or case.created_at)`. Cases with a real `triage_at` are counted from it as before.

**Tests:** `tests/case/test_case_scheduled.py` now has 8 tests, and all pass. The whole `tests/case` directory passes too (23). The new close-reminder tests cover these cases:
- A case with no `triage_at` that is 10 days old gets the reminder.
- A case with no `triage_at` that is 2 days old doesn't.
- A real `triage_at` takes priority over `created_at`.
- Nothing is sent on a non-Monday.

With the source fix stashed, the fallback test fails along with the earlier Monday test, so it catches the regression.

**Test setup:** `scheduler.add` returns `None`, so `scheduled.case_close_reminder` is `None` at import time. The tests fetch the function from `scheduler.registered_tasks` and unwrap the decorators.

**Not changed:** `case_stable_reminder` skips cases with no `stable_at` silently, and I left it alone because you asked about the close reminder. The same fallback to `created_at` would apply there. Say so if you want it.

----- next turn -----

**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added a helper, `_is_reminder_day()`. It compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). The check could never be true on any day, so `case_close_reminder` and `case_stable_reminder` stopped sending. The daily triage reminder doesn't use the helper, so it was unaffected.
- **Deploy:** image `main-81d8ae42` went to production on 2025-08-13 at about 16:40Z. The previous image, `main-b05613b5`, was running from 2025-07-30 and didn't have the helper.
- **Evidence:** the scheduler log shows close reminders sent on Mondays 07-28, 08-04 and 08-11. Monday 08-18 is the first Monday after the deploy, and it has no case close or stable reminders.
- **Fix:** the helper now uses `weekday() == calendar.MONDAY`. I added a regression test that fails on the old code.
- **Second issue:** the evening `TypeError` came from triage cases with no `triage_at`. That timestamp is only set in the New→Triage and Closed→Triage transition flow, so cases that entered triage another way never had it. The close reminder now counts from `created_at` when `triage_at` is missing. I added tests, and all of `tests/case` passes (23).
- **Status:** both fixes are uncommitted in the working tree. I haven't committed or deployed anything. `case_stable_reminder` still skips cases with no `stable_at`, which I left alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at