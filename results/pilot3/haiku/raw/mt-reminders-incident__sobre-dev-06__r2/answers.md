**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the Monday check with a helper that can never be true:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's `calendar` numbers Monday as 0). I checked this: on 2025-08-18 the comparison is `1 == 0`, so `_is_reminder_day()` is always False. Both weekly reminders, the triage close reminder (`case_close_reminder`) and the stable one (`case_stable_reminder`), gate on it, so neither sends. The daily `case_triage_reminder` doesn't use it, which is why those keep arriving.

The original code compared `isoweekday() == 1`, which was correct. The refactor replaced the literal 1 with `calendar.MONDAY`, and that broke it.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to the scheduler and web pods on 2025-08-13 at 16:40 UTC. Commit `c509d45e` is an ancestor of `81d8ae42`, so it shipped in that deploy.

**Evidence from the logs:**
- Monday 2025-08-11 (still on the previous image, `main-b05613b5`) sent close reminders normally, including to stable and triage cases.
- Monday 2025-08-18 (first Monday on `main-81d8ae42`) sent zero "Case close reminder" lines. The daily triage reminders still ran that day.
- Before that, the scheduler log had 15 "Case close reminder sent" lines, all on Mondays 07-28 and 08-04 and 08-11 (no sends appear on any other day).

**Things that aren't the cause, but you'll see them in the logs:**
- `case_stable_reminder` crashed with `TypeError` on cases where `stable_at` is None from 07-28 until the 08-13 deploy. `32fa810f` (merged 08-11, in `81d8ae42`) added the `if case.stable_at:` guard, so that error is gone. Because the loop catches per case, the other cases still got reminders, so the crash didn't stop the weekly sends.
- `case_close_reminder` still raises `TypeError` on `case.triage_at` being None (`scheduled.py:47`, logged every day since 07-28, including 08-18). Each case is caught separately, so only the cases with a null `triage_at` are skipped. It has no guard like the stable one, so it's worth fixing alongside the weekday bug.

**Suggested fix (not applied):** use `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based like `calendar`), or go back to `isoweekday() == 1`. You may also want a test that pins Monday, since nothing caught this before it reached production. I haven't made any changes to the code.

----- next turn -----

The weekly reminder check works again: `_is_reminder_day()` now compares Python's 0-based `weekday()` against `calendar.MONDAY`, and the new regression test fails on the old code and passes on the fix.

**The fix** (`src/dispatch/case/scheduled.py:33`): `date.today().isoweekday() == calendar.MONDAY` became `date.today().weekday() == calendar.MONDAY`. Both sides are now 0-based, so Monday matches again. Both weekly reminders (triage and stable) go through this helper, so both are restored.

**The regression test** (new file `tests/case/test_case_scheduled.py`): it freezes `date.today()` in the scheduled module and checks `_is_reminder_day()` for Monday 2025-08-11 (expects True) and for Tuesday through Sunday (expects False).
- Against the pre-fix code, the Monday case fails and the other six pass.
- With the fix, all seven pass.

**Test results:** `python -m pytest tests/case` gives 22 passed, run against the local PostgreSQL.

I haven't run the full test suite, and I haven't committed. The change is in the working tree (`git diff` shows the one-line fix plus the new test file) for you to review.

----- next turn -----

The evening `TypeError` is fixed: cases with no `triage_at` now count their weekly reminder from `created_at`, and the new tests pass against PostgreSQL.

**The cause:** `triage_at` is set only in `case_triage_status_flow`, and the status dispatcher's `(_, CaseStatus.triage)` catch-all never calls it. It logs a warning and returns, so a case that reaches Triage through that branch never gets a timestamp. The 2022 migration that added `triage_at` also didn't backfill existing cases, so older cases in Triage are null too. Then `datetime.utcnow() - case.triage_at` raises for every such case each evening, and the per-case handler logs it.

I couldn't confirm from the logs which path produced the null rows in production. The "Unexpected previous state" warning doesn't appear in either log file, and I didn't query the database. Those null cases are also why the job was logging the error every day.

**The fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the job now counts from `case.triage_at or case.created_at`. I didn't change the stable reminder. It skips a case with no `stable_at` entirely, so those cases still get no reminder. Tell me if you want that changed too.

**Tests** (`tests/case/test_case_scheduled.py`, now 10 tests in the file):
- Counts from `triage_at` when it is set.
- Falls back to `created_at` when `triage_at` is null. This test fails on the old code with the same `TypeError` from the logs.
- Skips a case with no `triage_at` that was created less than a week ago.
- The earlier weekday tests still pass.

`python -m pytest tests/case` gives 25 passed.

Two details in the tests. `scheduler.add` doesn't return the function, so the tests look the job up in `scheduler.registered_tasks`. `CaseFactory` ignores a `status=` argument, so the helper sets the status after creation.

Nothing is committed. Changes are in `src/dispatch/case/scheduled.py` and the new test file.

----- next turn -----

Here's the recap for the incident report.

**Summary**

Since the Monday 2025-08-18 run, the weekly close reminders (for cases in triage and cases marked stable) have not been sent. The daily triage reminders kept arriving, which is why the change was easy to miss.

**Root cause**

Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`, which compared `date.today().isoweekday()` (Monday is 1) against `calendar.MONDAY` (Monday is 0). The comparison was never true, so both weekly reminder jobs stopped sending. The original code compared against `1`, which was correct.

**Deploy**

Image `registry.example.com/dispatch:main-81d8ae42` went out to the scheduler and web pods on 2025-08-13 at 16:40 UTC. Commit `c509d45e` is an ancestor of that commit. The last Monday with sends was 2025-08-11, which ran on the previous image (`main-b05613b5`).

**Evening TypeError**

The triage close-reminder job logged `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` every evening, from 2025-07-28 onward. Cases in Triage with no `triage_at` caused it. `triage_at` is set only by `case_triage_status_flow`, and the status dispatcher's catch-all branch for transitions into Triage never calls it. The 2022 migration that added the column also didn't backfill it. I could not confirm which path produced the null rows in production, because the "Unexpected previous state" warning doesn't appear in either log file.

**Fixes and tests (uncommitted)**

- `src/dispatch/case/scheduled.py`:
  - `_is_reminder_day()` now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`.
  - `case_close_reminder` counts from `triage_at or created_at`, so cases with no triage timestamp still get their weekly reminder.
- `tests/case/test_case_scheduled.py` (new, 10 tests):
  - The weekday check, Monday and each other day.
  - The reminder job counting from `triage_at`, falling back to `created_at`, and skipping a recent case with no `triage_at`.
  - The weekday regression test and the fallback test each fail on the pre-fix code.
- `python -m pytest tests/case` passes (25 tests) against the local PostgreSQL.

**Open items**

- `case_stable_reminder` still skips cases with no `stable_at` entirely rather than falling back to another timestamp. I left it alone because you asked only about the triage job.
- The catch-all branch for transitions into Triage should probably set `triage_at`. That would stop new null rows, but it doesn't backfill existing ones.
- Nothing is committed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at