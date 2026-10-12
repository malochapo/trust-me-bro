**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The original code compared `isoweekday()` to `1`, which is Monday in ISO numbering (Monday=1 through Sunday=7). `calendar.MONDAY` is `0` (Monday=0 through Sunday=6). Mixing the two conventions makes the check true only on a day that never occurs as an ISO weekday, so it is never true. I confirmed both values locally: `calendar.MONDAY` is 0, and 2025-08-18 (a Monday) has `isoweekday()` of 1.

The bug affects both reminders that call `_is_reminder_day()`:
- `case_close_reminder` (long-running triage cases)
- `case_stable_reminder` (long-running stable cases)

`case_triage_reminder` doesn't use the weekly check, which is why the daily triage reminders still arrive.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`. The scheduler container started with it at 2025-08-13T16:40:06Z (the web container too, at 16:40:07Z). `c509d45e` is an ancestor of `81d8ae42` (`git merge-base --is-ancestor` confirms this). The commit that shipped it is `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)", David Whittaker), which carried the earlier `c509d45e` commit along with it.

**Log evidence:**
- Monday 2025-08-11 (before the deploy): "Case close reminder sent" appears for several cases, and stable reminders ran.
- Monday 2025-08-18 (after the deploy): no "Case close reminder sent" lines at all. Only the incident close reminder fired.

**Side note:** the `case_stable_reminder` errors (`datetime - NoneType` on `case.stable_at`) in the logs from 07-28 to 08-10 came from the code before `32fa810f`. That fix landed on 08-11 and is not the cause of the current silence.

No code was changed. The fix would be to compare against the same numbering as the original, either `date.today().isoweekday() == 1` or `date.today().weekday() == calendar.MONDAY`. Want me to make that change and add a test?

----- next turn -----

The reminder bug is fixed and covered by a regression test. The full suite has 8 failures, but they fail the same way on the original commit, so they predate this change.

**The fix** (`src/dispatch/case/scheduled.py`, one line):

```python
return date.today().weekday() == calendar.MONDAY
```

`weekday()` and `calendar.MONDAY` both use Monday=0, so the comparison is correct. This restores the weekly close reminders for both long-running triage and stable cases. The daily triage reminders were never affected.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it fixes `date.today()` to each day of the week 2025-08-11 through 08-17 and asserts that `_is_reminder_day()` is true only on Monday.
- With the buggy line restored, the Monday case fails.
- With the fix, all 7 cases pass.

**Full suite** (`python -m pytest`): 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. Running those same tests against the original commit gives the same 8 failures, so I left them alone.

Nothing is committed. Let me know if you want me to commit the change.

----- next turn -----

The close-reminder TypeError is fixed, and a test covers it. Cases that have no `triage_at` now count their weeks from `created_at` and still get the weekly reminder.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some cases in triage have `triage_at` set to `NULL`, so the subtraction raises the TypeError. The job catches it per case, which is why it logs an error every evening instead of failing the whole run. The log shows 40 of these between 07-28 and 08-20.

**Fix** (`src/dispatch/case/scheduled.py`):

```python
# some triage cases never had triage_at set, so count from creation
triage_started_at = case.triage_at or case.created_at
span = datetime.utcnow() - triage_started_at
```

**Tests** (`tests/case/test_case_scheduled.py`):
- A triage case with no `triage_at` and created 8 days ago gets the reminder.
- A triage case with no `triage_at` and created 2 days ago does not.
- A case with `triage_at` set uses that timestamp, not `created_at`.

The first test fails when the fallback is removed, and all 10 tests pass with it. The full suite has the same 8 pre-existing failures as before (AI service, one database test, one entity test), and nothing new fails. Nothing is committed.

**Left alone:** `case_stable_reminder` has no TypeError. It already skips cases where `stable_at` is missing, so those cases get no weekly reminder at all. You asked only about the close job, so I didn't change that path. If you want stable cases to fall back to `created_at` too, that's a one-line change.

----- next turn -----

## Recap

**Weekday bug.** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`, which compared `date.today().isoweekday()` against `calendar.MONDAY`. ISO weekdays number Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both weekly close reminders (long-running triage and stable cases) stopped. The daily triage reminders don't use this check and kept sending. The fix compares `date.today().weekday()` to `calendar.MONDAY`. The regression test in `tests/case/test_case_scheduled.py` fails on the old comparison and passes on the fix.

**Deploy.** `c509d45e` shipped in `main-81d8ae42`. The scheduler started that image at 2025-08-13T16:40Z. The Monday before the deploy (2025-08-11) still sent close reminders. The first Monday without them was 2025-08-18.

**Evening TypeError.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at` set to NULL, so the subtraction raised a TypeError. The job catches the error per case, so it logged one each evening (40 in the logs) without stopping the run. The fix counts from `case.created_at` when `triage_at` is missing. Three tests cover it: a case with no `triage_at` created 8 days ago gets the reminder, one created 2 days ago doesn't, and a case with `triage_at` set uses that value.

**Not changed:** `case_stable_reminder` has no TypeError because it already skips cases with no `stable_at`, so those cases get no weekly reminder. The fixes are uncommitted. The full suite has 8 failures in AI service, one database test, and one entity test, and they fail the same way on the original commit.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```