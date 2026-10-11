I've confirmed the cause and I'm writing it up now. I haven't changed any code.

## Root cause

Commit **`c509d45e`**, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check. It replaced the inline test in `src/dispatch/case/scheduled.py` and used the wrong constant:

```python
# before
date.today().isoweekday() == 1
# after
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (I checked it in Python). `isoweekday()` returns 1–7, with Monday as 1, so it is never 0. `_is_reminder_day()` is therefore always `False`.

`case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both use this check, so neither sends again. The fix is `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`. The cleaner option is probably to compare `weekday()` against `calendar.MONDAY`.

## Evidence from the logs

- "Case close reminder sent" appears only on Mondays 2025-07-28 (4), 08-04 (6) and 08-11 (5). Monday 08-18 has none.
- On 08-18 the 18:00 jobs ran, since the timing lines are logged, but nothing was sent.
- The daily triage reminders go through `case_triage_reminder`, which doesn't use the Monday check. That is why they kept arriving.
- The traceback line numbers shift by 4 from line 43 to line 47 on 08-18. That matches the 4 lines the refactor added, so the new code was running.

## The deploy

- On **2025-08-13 at 16:40Z**, a new scheduler pod `scheduler-mhtsgqwwx-q5q2n` started with image `registry.example.com/dispatch:main-81d8ae42`. The web pod started at the same time with the same image.
- The previous deploy was on 2025-07-30 at 17:10Z, with image `main-b05613b5`.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", a small change to `service.py`. It is the tip of `main` as of 08-12, and `c509d45e` is in the range `b05613b5..81d8ae42`.
- So the bug shipped in the **2025-08-13 16:40Z deploy of `main-81d8ae42`**. That is about 26 commits after `b05613b5`, and it was the first production release to include `c509d45e`.

## Unrelated issue

The log also shows a `TypeError` on every run: `datetime - None`, from `case.triage_at` being `None` in `case_close_reminder`. The error is caught per case. It is not the cause of the missing reminders, because it predates the deploy and the 07-28, 08-04 and 08-11 Mondays still sent reminders. It does mean some triage cases without `triage_at` never get reminders. The stable-case version of that bug was fixed in `32fa810f`, but the triage version wasn't.

## Impact

Monday 08-18 was the only Monday the broken code ran in these logs, and the logs end on 08-20. Production has probably missed every Monday since 08-18.

Do you want me to prepare the fix, plus a regression test that patches `date.today` to a Monday?

----- next turn -----

I fixed the Monday check and added a regression test. All 13 new tests pass, and so do the 28 tests in `tests/case`. I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` now returns `date.today().weekday() == calendar.MONDAY`. Before, it compared `isoweekday()` with `calendar.MONDAY`. Those use different numbering (Monday is 1 and 0), so the check never matched.

**Tests** (`tests/case/test_case_scheduled.py`, new):
- `_is_reminder_day()` is `True` on Monday and `False` on the other six days, with `date.today` patched.
- `case_stable_reminder` and `case_close_reminder` each send on a Monday for a case older than a week. They send nothing on a Tuesday or a Sunday.
- The tests find those functions through the scheduler's registered tasks and unwrap the decorators. They use mocks, so no database is touched.

I ran the new tests against the old code too. The three Monday cases fail there (`_is_reminder_day`, stable, close), so the tests would have caught the original bug.

Production will keep missing the Monday reminders until this is deployed.

The unrelated `triage_at is None` error is still there in `case_close_reminder`. Cases without `triage_at` still won't get reminders. I left it alone because you asked only for this fix, so tell me if you want it handled too.

----- next turn -----

`case_close_reminder` no longer raises the TypeError, and cases without `triage_at` now get their weekly reminder. The new test and the 30 tests in `tests/case` pass. Nothing is committed.

**Cause:** `case.triage_at` is `None` for some triage cases, so `datetime.utcnow() - case.triage_at` raises `TypeError`. The job's per-case `try/except` logs the error and moves on, so each of those cases was skipped silently. That is the traceback at line 47 (line 43 before the 08-13 deploy) in the logs.

`triage_at` is only set by `case_triage_status_flow` in `src/dispatch/case/flows.py`, when a case moves into triage. A case that is in triage but never went through that flow keeps `NULL`. That includes cases that were already in triage before the column was added; the migration just added a nullable column with no backfill. I can't tell from the logs alone which of those cases are in production, so check the database if you want to know how many there are.

**Fix** (`src/dispatch/case/scheduled.py`): the job now counts from `case.triage_at or case.created_at`.

**Test** (`tests/case/test_case_scheduled.py`): a triage case with `triage_at=None`, run on a Monday:
- Created 10 days ago, it sends one reminder.
- Created 3 days ago, it sends none.
- In both runs nothing is logged as an exception.

I ran the new tests against the old code. The two fallback cases fail there, along with the Monday tests, because the stash also reverted the earlier Monday fix.

I left `case_stable_reminder` alone. It already skips stable cases that have no `stable_at` (commit `32fa810f`), so those cases still get no reminder. Do you want the same fallback to `created_at` there?

----- next turn -----

## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()`. It compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check never matched and the weekly reminders were never sent. The daily triage reminder doesn't use that check, which is why it kept working.

**Deploy:** Image `main-81d8ae42` went to production on 2025-08-13 at 16:40Z, replacing `main-b05613b5` from 2025-07-30. It was the first release to include `c509d45e`.

**Impact:** Reminders were sent on Mondays 07-28, 08-04 and 08-11. Monday 2025-08-18 was the first Monday after the deploy, and the logs show the jobs ran but sent nothing. The logs end on 08-20, so later Mondays are not covered, but they were almost certainly missed too.

**Fix:** `_is_reminder_day()` now uses `weekday()`. I added `tests/case/test_case_scheduled.py`. It covers every weekday, and it checks both reminder jobs on Monday, Tuesday and Sunday. It fails on the old code. The fix is uncommitted and not deployed, so production is still affected until it ships.

**Separate issue:** `case_close_reminder` logged a `TypeError` every evening. It was `datetime.utcnow() - case.triage_at` with `triage_at` set to `None`. Only the transition into triage sets that field, so cases that never went through it were skipped silently. The job now counts from `created_at` when `triage_at` is missing. This predates the weekday bug, so it was not a cause of the missed reminders on or after 08-18. It is also fixed in my working tree only, with a test.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at