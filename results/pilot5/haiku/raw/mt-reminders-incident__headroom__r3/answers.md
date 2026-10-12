**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It moved the test into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` is 1 for Monday, but `calendar.MONDAY` is 0 (Python's `weekday()` numbering). The comparison is never true, so `case_close_reminder` and `case_stable_reminder` never send. The original code compared against `1` and was correct. `case_triage_reminder` has no weekday check, which is why the daily triage reminders still arrive.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on 2025-08-13 at 16:40 UTC for both `web` and `scheduler` (api.log:13201, scheduler.log:18851). `c509d45e` is an ancestor of `81d8ae42` ("fix(case): exclude resolved_by in update", 2025-08-12). That is the only deploy in the logs after the refactor, and the previous one was `main-b05613b5` on 2025-07-30.

**Log evidence:**
- Close-reminder sends happened on Mondays 2025-08-04 (6) and 2025-08-11 (5), both before the deploy.
- No close-reminder sends happened on Monday 2025-08-18. The stable reminder also had no successful sends in the window.
- Triage reminders kept sending daily through 2025-08-20.

**Separate issue, not the cause:** from 2025-07-28 to 2025-08-08 the stable reminder logged a `datetime - NoneType` error daily for cases with no `stable_at`. Commit `32fa810f` (2025-08-11) fixed that with an `if case.stable_at:` guard. It is in the same deploy, so it doesn't explain the mid-August gap.

**Caveats:** the deploy tag is inferred from the image name `main-81d8ae42`, and I did not check it against the registry or the deploy pipeline. The logs don't show which build each Monday's sends came from, but the timing matches the refactor exactly.

**Suggested fix (not applied):** use `date.today().weekday() == calendar.MONDAY`, which is 0-based and matches the calendar constant, or restore `date.today().isoweekday() == 1`. Add a test that pins a known Monday date, because nothing in the test suite caught this.

No code was changed.

----- next turn -----

The reminder bug is fixed and there's a regression test for it. The suite still has 8 failures, all in AI, database, and entity tests. Those fail without my change too, so they're unrelated.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` are both 0-based, so Monday matches again. The old `isoweekday()` was 1-based, which is what broke it.

**Regression tests** (new file `tests/case/test_case_scheduled.py`, 11 tests):
- `_is_reminder_day()` returns True only on Monday, checked across a full week with a patched "today".
- `case_stable_reminder` and `case_close_reminder` each send on a Monday for a case stale for 8 days, and don't send on Tuesday.

I checked that the test catches the bug. With the old line back in, the three Monday tests fail. With the fix in, all 11 pass, and the case module runs 26 passing tests.

**Full suite:** 370 passed, 8 failed, 4 skipped. The same 8 fail with the fix stashed, so my change didn't cause them. They are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. I didn't investigate them.

**Test notes:**
- `scheduler.add` returns `None`, so the tests look up tasks in `scheduler.registered_tasks` and call the undecorated function.
- `CaseFactory` ignores `status=` passed as a kwarg, because `Params` sets it to `"New"`. The tests set `case.status` after creating the case, the same way `test_case_messaging.py` does.

Nothing is committed. The changes are in the working tree: one line in `scheduled.py` plus the new test file.

----- next turn -----

The close reminder TypeError is fixed. Cases with no `triage_at` now count from `created_at`, and a regression test covers it.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some triage cases have no `triage_at`, so the subtraction raised `TypeError` and the per-case `except` logged it. The deployed scheduler logs show 24 of these from the close job (16 at the deployed line 43, 8 at line 47), from 2025-07-28 onward. The `case_stable_reminder` errors in the same logs were a different `None` timestamp, `stable_at`, and that was fixed earlier by `32fa810f`.

**Fix** (`src/dispatch/case/scheduled.py`, in `case_close_reminder`):
```python
# cases without a triage timestamp count from when they were created
triaged_at = case.triage_at or case.created_at
span = datetime.utcnow() - triaged_at
```
Both columns are already loaded by `get_all_by_status`, so there is no extra query.

**Tests** (added to `tests/case/test_case_scheduled.py`):
- A triage case with no `triage_at` and created 8 days ago gets a reminder on Monday.
- A triage case with no `triage_at` and created 2 days ago gets no reminder.

Against the old code, the first test fails. The second passes either way, because the old code's error was swallowed by the `except` and nothing was sent. With the fix, all 28 tests in `tests/case` pass.

**Open question:** `case_stable_reminder` still skips cases with no `stable_at`, because of the guard from `32fa810f`. Those cases never get a weekly stable reminder. You asked for the fallback only on the close reminder, so I didn't change the stable job. If you want the same `created_at` fallback there, tell me and I'll make it the same way.

Nothing is committed.

----- next turn -----

## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. Daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`, which compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was never true, so the close and stable reminders never sent. `case_triage_reminder` has no weekday check, so it kept working.

**Deploy:** Image `main-81d8ae42` started for both `web` and `scheduler` on 2025-08-13 at 16:40 UTC. Commit `c509d45e` is an ancestor of `81d8ae42`. This is the only deploy after the refactor. The image-to-commit mapping comes from the image tag and was not checked against the registry.

**Evidence:** Close-reminder sends happened on Mondays 2025-08-04 and 2025-08-11, both before the deploy. None happened on 2025-08-18, the first Monday after the deploy.

**Fix:**
- `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.
- `case_close_reminder` counts from `created_at` when `triage_at` is missing, so those cases get their weekly reminder.

**Tests:** `tests/case/test_case_scheduled.py` has 13 tests. They cover the weekday check across a full week, the stable and close reminders on Monday and on other days, and the `created_at` fallback. Against the old code, the Monday and fallback tests fail. With the fix, all 28 tests in `tests/case` pass. The full suite has 8 failures in AI, database, and entity tests. They also fail without my change, so they are unrelated.

**Not changed:**
- `case_stable_reminder` still skips cases with no `stable_at`, so those cases get no weekly stable reminder. You asked for the fallback only on the close job. Say if you want the same `created_at` fallback there.
- Nothing is committed. The changes are in the working tree.

---

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at