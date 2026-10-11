**Root cause:** commit `c509d45e` broke the Monday check. The weekly reminders have been dead since then.

In `src/dispatch/case/scheduled.py:31-33`, the refactor added:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (Monday-based, with `weekday()` numbering), but `isoweekday()` returns `1` for Monday (ISO numbering, 1–7). I confirmed both values in Python. The condition is therefore never true, so `case_close_reminder` and `case_stable_reminder` never reach `send_case_close_reminder` on any day. The original code compared `isoweekday() == 1`, which was correct. The triage reminder has no Monday gate, which is why it still fires daily.

**Deploy that shipped it:** `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") first reached production in image `registry.example.com/dispatch:main-81d8ae42`, which the scheduler started on 2025-08-13 at 16:40 (scheduler.log:18851). `81d8ae42` is `fix(case): exclude resolved_by in update (#6183)`, and `c509d45e` is an ancestor of it. The image tag appears to be the commit SHA prefix, though I didn't check the deploy pipeline to confirm that mapping.

**Log evidence:**
- Monday 2025-08-11 ran under the older image `main-b05613b5` (deployed 2025-07-30, before the refactor). It sent 6 `Case close reminder sent` entries.
- Monday 2025-08-18 ran under `main-81d8ae42`. It sent zero case close or stable reminders. Only triage and incident reminders went out.

**Secondary issue (not the cause):** `case_close_reminder` logs a `TypeError` when `case.triage_at` is None (e.g. scheduler.log:15474, 2025-08-10; again on 2025-08-18 at line 25269). The per-case `try/except` contains it, so it doesn't stop the other cases. The stable-reminder version of this crash was fixed by `32fa810f`, but `case_close_reminder` has no equivalent guard.

**Suggested fix (not applied, per your instruction):** change the check to `date.today().weekday() == calendar.MONDAY` (or `isoweekday() == 1`). Also add `triage_at` to the `None` guard in `case_close_reminder`. A test that pins `_is_reminder_day()` to a known Monday would have caught this.

I didn't change any code, and I didn't check whether the test suite covers this function.

----- next turn -----

The weekly reminder gate now works, and a regression test covers it. The changes are uncommitted in the working tree.

**Fix:** `src/dispatch/case/scheduled.py:33` now reads `date.today().weekday() == calendar.MONDAY`. Both sides use Monday-is-0 numbering. The buggy version compared `isoweekday()` (Monday is 1) against `calendar.MONDAY` (0), so it never matched.

**Regression test:** `tests/case/test_case_scheduled.py` pins `date.today()` to each day from Monday 2025-08-11 through Sunday 2025-08-17 and asserts `_is_reminder_day()` is true only on Monday.

**Verification:**
- New test file: 7 passed with the fix.
- With the old line restored, the Monday case fails (`test_is_reminder_day[day0-True]`), so the test catches this bug.
- `python -m pytest tests/case`: 22 passed.

**Not changed:** the `case_close_reminder` crash when `case.triage_at` is None, which I noted earlier. It's contained by the per-case `try/except` and doesn't stop the weekly reminders, so I left it out of this fix. It's a one-line guard like the one `case_stable_reminder` already has, if you want it in the same change.

----- next turn -----

The close reminder no longer crashes on triage cases without `triage_at`, and those cases now count from `created_at`. The changes are uncommitted.

**Cause:** `triage_at` was added in migration `2022-08-01_391f7c3e6992` with no backfill, so triage cases that existed before then have NULL there. The only other place that sets it is the background `case_triage_status_flow`, so a failed or skipped transition also leaves it NULL. The job then runs `datetime.utcnow() - None`. That raises a TypeError before the Monday check, so it fires every evening, and the per-case `try/except` logs it and moves on. The logs don't include case IDs, and I can't query the production database, so I can't say how many cases are affected.

**Fix** (`src/dispatch/case/scheduled.py:47-50`): `triage_started_at = case.triage_at or case.created_at`, with a comment explaining the fallback.

**Tests** (`tests/case/test_case_scheduled.py`): I added three tests that run the job body against real triage cases:
- A triage case with no `triage_at` that was created 8 days ago gets a reminder.
- A triage case with no `triage_at` created 2 days ago does not.
- A case whose `triage_at` is 2 days old, but was created 30 days ago, does not. This checks that `triage_at` still wins when it is set.

The job is called through `scheduler.registered_tasks`, since the decorator doesn't return the function. The `CaseFactory` ignores a `status` argument, so the tests set the status after creating the case.

**Verification:** all 10 tests in the file passed, and `python -m pytest tests/case` gave 25 passed. With the fallback removed, the 8-day test fails, so it catches the TypeError.

**Not changed:** `case_stable_reminder` already skips cases with no `stable_at` rather than falling back to a date. I left it as it was, since you asked about the close reminder only.

----- next turn -----

Both bugs are fixed in the working tree, and nothing is committed. The weekday check at `src/dispatch/case/scheduled.py:33` and the close reminder's `triage_at` fallback at lines 47-50 are the two changes. Regression tests cover both: `tests/case/test_case_scheduled.py` has 10 tests, all passing, and `python -m pytest tests/case` gives 25 passed.

What happened:
- **Missing Monday reminders:** commit `c509d45e` (2025-08-12) replaced `isoweekday() == 1` with `isoweekday() == calendar.MONDAY`, but `calendar.MONDAY` is 0. The Monday check could never be true, so case close and stable reminders stopped. The daily triage reminder has no Monday check, so it kept going.
- **Evening TypeError:** `triage_at` was added in 2022 without a backfill, and it is only set by a background flow. Triage cases without it made `datetime.utcnow() - None` fail every evening. The job now counts those cases from `created_at`.
- **Deploy:** the scheduler started running image `main-81d8ae42` on 2025-08-13 at 16:40, which contains `c509d45e`. The Monday 2025-08-11 run was on the older image and sent six close reminders. The Monday 2025-08-18 run sent none.

Caveats: the logs don't include case IDs, so I can't say how many cases hit the TypeError. I also haven't confirmed the image-tag-to-commit mapping against the deploy pipeline.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at