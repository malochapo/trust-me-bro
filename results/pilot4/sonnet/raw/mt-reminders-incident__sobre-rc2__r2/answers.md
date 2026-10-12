**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check in `src/dispatch/case/scheduled.py`. It was shipped to production in the deploy of image `main-81d8ae42` on 2025-08-13 at 16:40Z.

**What the commit did.** It swapped the inline check `date.today().isoweekday() == 1` for a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` against `calendar.MONDAY`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The helper therefore returns `True` only when `isoweekday()` is 0, which never happens. `case_close_reminder` (triage cases) and `case_stable_reminder` both gate on `q >= 1 and _is_reminder_day()`, so neither reminder ever fires. `case_triage_reminder` has no weekday gate, which is why the daily triage reminders still arrive. The refactor was meant to be behaviour-neutral, so nobody noticed.

**Evidence from the logs**
- "Case close reminder sent" appears on the Mondays 2025-07-28 (4 times), 2025-08-04 (6) and 2025-08-11 (5). It does not appear at all on 2025-08-18, the first Monday after the deploy. The daily triage reminders continue through 2025-08-20.
- The deploy is visible as a kubelet "Started container … image registry.example.com/dispatch:main-81d8ae42" line in both logs at 2025-08-13T16:40Z. The pods are new: `scheduler-mhtsgqwwx-q5q2n` in the scheduler log and `web-5dkmr9s9s-xxktx` in the API log.
- The previous image was `main-b05613b5`, deployed 2025-07-30T17:10Z. It predates the refactor, and it was the one sending the reminders on the August 4 and 11 Mondays.
- `81d8ae42` (the tip of the deployed image, "fix(case): exclude resolved_by in update", #6183) contains `c509d45e`; `b05613b5` does not. The other commits in that range are unrelated.

**Not the cause.** The `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors in `case_stable_reminder` and `case_close_reminder` on 2025-07-28 come from cases with no `stable_at` or `triage_at`. That is the separate, already-fixed bug from `32fa810f`, and it is not what stopped the reminders.

**Suggested fix (not applied, per your instruction).** Compare against the ISO weekday explicitly, for example `date.today().weekday() == calendar.MONDAY`. Alternatively, restore `isoweekday() == 1`. A small unit test of `_is_reminder_day()` with a frozen Monday date would have caught this.

----- next turn -----

I fixed the Monday check, and the new regression test passes with the fix. Without the fix, the two Monday cases of the test fail. I ran only the new test file, not the whole suite. Nothing is committed.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` both count Monday as 0, so the check now matches Mondays. Before, `isoweekday()` was compared against 0, which never matches.
- **Test:** `tests/case/test_case_scheduled.py` patches `date.today()` and checks the Mondays 2025-08-11 and 2025-08-18, which must return true. It also checks a Tuesday, a Wednesday and a Sunday, which must return false.

The fix only takes effect once it is deployed. The Mondays missed since 2025-08-18 won't be backfilled; reminders resume on the first Monday after the deploy.

----- next turn -----

The TypeError comes from cases that are in triage but have no `triage_at`. I fixed the close reminder job and added a test. All 8 tests in the new file pass with both fixes, and the same file fails 4 of 8 without them. I didn't run the full suite, and I couldn't lint or format-check because `ruff` isn't installed here. Nothing is committed.

**Cause.** `triage_at` is a nullable column. The only place that sets it is the status-transition code (`src/dispatch/case/flows.py:595`). A case that is created directly in triage status never goes through a transition, so `triage_at` stays null. `case_close_reminder` then runs `datetime.utcnow() - case.triage_at`, which raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The job catches the error per case and logs it, so you see it every evening (16 occurrences in the logs), and those cases never get their weekly reminder.

**Fix.** In `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`, with a comment explaining why. Cases without `triage_at` now get the weekly reminder once they are more than a week old.

**Tests.** I added three cases to `tests/case/test_case_scheduled.py`. All three also check that no exception is logged:
- A missing `triage_at` with a case created 10 days ago sends the reminder.
- A missing `triage_at` with a case created 2 days ago does not.
- When `triage_at` is set, it is used instead of `created_at`.

**Open question.** `case_stable_reminder` has the same shape of problem, but commit `32fa810f` made it skip cases with no `stable_at` instead of falling back. I left it alone since you only asked about the close job. If you want stable cases to fall back to `created_at` too, say so and I'll change it.

----- next turn -----

**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving because that job has no weekday check.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) replaced the inline check `isoweekday() == 1` with a helper, `_is_reminder_day()`. The helper compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so it never returned true. Both `case_close_reminder` and `case_stable_reminder` call it, so neither job sent anything.
- **Deploy:** image `main-81d8ae42` went out at 2025-08-13T16:40Z and contains that commit. The previous image, `main-b05613b5`, did not, and it sent the reminders on 2025-08-04 and 2025-08-11. No close reminders appear in the logs on 2025-08-18, the first Monday after the deploy.
- **Fix:** `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`. A parametrized regression test covers Mondays, a Tuesday, a Wednesday and a Sunday.
- **Separate TypeError:** `case_close_reminder` logged `datetime - NoneType` every evening. Cases created directly in triage never get `triage_at`, because it is only set on status transitions. The job now counts from `triage_at or created_at`, so those cases get their weekly reminder. Three tests cover the change.
- **Caveats:** the fix needs a deploy to take effect, and the Mondays missed since 2025-08-18 are not backfilled. I ran only the new test file (8 tests, all passing), not the full suite, and `ruff` isn't installed here, so nothing was linted. Nothing is committed. `case_stable_reminder` still skips cases with no `stable_at` rather than falling back to `created_at`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at