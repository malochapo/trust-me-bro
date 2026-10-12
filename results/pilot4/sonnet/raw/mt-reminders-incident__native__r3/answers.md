**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check. It was shipped to production on 2025-08-13 in image `main-81d8ae42`.

**The bug.** The refactor moved the old check `date.today().isoweekday() == 1` into a new helper, `_is_reminder_day()`. The helper in `src/dispatch/case/scheduled.py:31-33` compares against `calendar.MONDAY`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

- **Wrong constant:** `calendar.MONDAY` is `0`, because the `calendar` module numbers weekdays from 0.
- **Never true:** `isoweekday()` returns 1 to 7, with Monday as 1, so the comparison can never be true.
- **Where it applies:** both `case_close_reminder` (triage cases) and `case_stable_reminder` use the helper, so both weekly reminders stopped.
- **Why daily reminders still work:** `case_triage_reminder` doesn't use the helper, which matches what you're seeing.
- **No error logged:** nothing fails, so the weekly reminders just silently stop.

**Evidence from the logs.**
- "Case close reminder sent" appears only on Mondays 07-28, 08-04 and 08-11, with 4, 6 and 5 sends. The last was 2025-08-11, and there are none on 08-18.
- Those sends were all on the old image, `main-b05613b5`.
- The scheduler pod restarted on 2025-08-13 at 16:40Z with `main-81d8ae42`, and the web pod restarted with the same image a second later.
- `c509d45e` is an ancestor of `81d8ae42` and `b05613b5` is not an ancestor of `c509d45e`, so the old image predates the refactor and the new one contains it.
- On `81d8ae42`, `_is_reminder_day()` is used at lines 49 and 95.
- The 08-13 deploy is the first one after the refactor. The refactor commit dates to 08-12, and the Monday 08-11 reminders were sent before it.

**Unrelated noise in the logs.** These are not the cause.
- Every day there are `unsupported operand type(s) for -: 'datetime' and 'NoneType'` errors from `case_stable_reminder` and `case_close_reminder`.
- The stable one is the missing `stable_at` that `32fa810f` fixed (2025-08-11).
- The error from `case_close_reminder` comes from a case with no `triage_at`. It first appears at line 51 on the old image and at line 55 on the new one. It means one case that has no `triage_at` raises an error, and it is a separate bug. I did not check whether that error skips the other cases' reminders.

**Fix, when you want it.** Compare against `1`, or against `calendar.MONDAY + 1`. A simpler option is `date.today().weekday() == calendar.MONDAY`. A small test that mocks a Monday date would have caught this. I haven't changed any code.

----- next turn -----

I fixed the Monday check and added a regression test. The `tests/case` suite passes (22 tests). I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py`, `_is_reminder_day`): it now uses `date.today().weekday() == calendar.MONDAY`. Both sides use the same numbering, with Monday as 0. Before, `isoweekday()` (Monday is 1) was compared against `calendar.MONDAY` (0), so the check never matched. This is a one-line change that keeps the shared helper from `c509d45e`, so both the triage and stable reminders are fixed.

**Test** (new file `tests/case/test_case_scheduled.py`): it fakes `date.today()` for each day of the week from Monday 2025-08-18 to Sunday 2025-08-24. It expects `_is_reminder_day()` to be true on Monday and false on the other six days. With the old code restored, the Monday case fails and the other six pass, so it would have caught the bug.

The fix only takes effect once a new image is deployed. The `NoneType` error from `case_close_reminder` (a case with no `triage_at`) is a separate bug and is unchanged.

----- next turn -----

The TypeError is fixed. The `tests/case` suite passes (24 tests), and nothing is committed.

**Cause.** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`, and `triage_at` can be empty. The `case_triage_status_flow` in `flows.py` only sets it when a case transitions into triage. A case that never went through that transition has no `triage_at`. That includes cases created directly in triage and older cases. The subtraction then raises the TypeError, which the per-case `except` logs and swallows, so those cases never got a reminder.

**Fix.** In `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`. It only sends the weekly reminder to cases older than a week, and only on Mondays, as before.

**Tests.** I added two to `tests/case/test_case_scheduled.py`:
- **Fallback:** cases with no `triage_at` are counted from `created_at`. A 10-day-old case gets the reminder and a 2-day-old one doesn't. Cases that do have `triage_at` behave as before.
- **Monday only:** a case that would otherwise qualify gets no reminder when it isn't a reminder day.

With the source change reverted, the fallback test fails. The Monday-only test needs the earlier fix from this session to stay in place.

`case_stable_reminder` still skips cases that have no `stable_at` instead of counting from `created_at`. You only asked for the close reminder, so I left it. Say if you want the same fallback there.

----- next turn -----

**Recap**

- **Symptom:** weekly Monday reminders for long-running triage and stable cases stopped in mid-August. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (2025-08-12), moved the Monday check into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` (Monday is 1) against `calendar.MONDAY` (which is 0). That is never true, so neither weekly reminder was sent and nothing was logged.
- **Deploy:** the scheduler and web pods restarted on 2025-08-13 at about 16:40Z with image `main-81d8ae42`, which contains the refactor. The Monday reminders on 08-04 and 08-11 were sent on the old image, `main-b05613b5`. The first Monday after the deploy was 2025-08-18, and no case close reminders were sent that day.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. I added a test covering all seven weekdays. With the old code, the Monday case fails.
- **Separate bug, the evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is empty for cases that never went through the transition into triage. The job logged a TypeError for them every evening and sent them no reminder. It now counts from `created_at` when `triage_at` is missing, and I added tests for that.
- **Not changed:** `case_stable_reminder` still skips cases without `stable_at` instead of counting from `created_at`.
- **Not yet in production:** both fixes are uncommitted and not deployed, so the reminders stay off until a new image ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at