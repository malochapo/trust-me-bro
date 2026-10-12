**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check.

The refactor added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

The old inline check was `date.today().isoweekday() == 1`. The two aren't equivalent:
- `isoweekday()` returns 1–7, with Monday = 1.
- `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0.
- The comparison is therefore never true, on any day.

`case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both gate on this helper, so both stopped sending. The daily triage reminder doesn't use the helper, which is why it kept working.

I confirmed `calendar.MONDAY == 0` and that 2025-08-18 has `isoweekday() == 1`, but I haven't run the helper itself.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, whose commit is "fix(case): exclude resolved_by in update (#6183)". It went out on 2025-08-13 at about 16:40Z. Both the scheduler pod (`scheduler-mhtsgqwwx`, 16:40:06) and the web pod (`web-5dkmr9s9s`, 16:40:07) started on that image. `c509d45e` is an ancestor of `81d8ae42` and is not in the previous image, `main-b05613b5`, which had been running since 2025-07-30.

**Log evidence:**
- "Case close reminder sent" lines appear only on the Mondays 07-28 (4), 08-04 (6) and 08-11 (5). Those all ran on the old code.
- On Monday 08-18, the first Monday after the deploy, there are zero sends. The close and stable reminder jobs ran at 18:00 without error on the stable side, but sent nothing.

**Related, but not the cause:**
- `case_close_reminder` logs a `TypeError` every day (`datetime - None`, from `case.triage_at`), both before and after the deploy. The per-case `try/except` catches it, so other cases still got reminders on 07-28, 08-04 and 08-11. It points to cases with no `triage_at`, which is a separate bug.
- The stable reminder's similar error stopped after the deploy. That is commit `32fa810f` ("not all cases have a stable_at date"), which went out in the same image.

**Suggested fix (not applied, as you asked):** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`, which also counts from 0. A small unit test on `_is_reminder_day()` with a known Monday would catch this class of bug.

I haven't saved anything to memory yet. I can write up these findings if you want them kept for later sessions.

----- next turn -----

I saved the findings to memory, so a new session can pick this up. The note is `weekly-case-reminder-regression.md`, and it's indexed in `MEMORY.md`. It records:
- **Root cause:** commit `c509d45e` compares `isoweekday()` (Monday = 1) to `calendar.MONDAY` (0), so the Monday check never passes.
- **Deploy:** image `main-81d8ae42`, rolled out 2025-08-13 at about 16:40Z.
- **Log evidence:** the log lines showing the reminders stopping after that deploy.
- **Unrelated finding:** the daily `triage_at` `TypeError` is separate from this bug.
- **Suggested fix:** use `weekday()` and add a unit test. It is not applied.

I haven't changed any code.

----- next turn -----

Fixed the weekday check, and `_is_reminder_day()` now returns true on Mondays. I also added a regression test.

**Cause:** commit `c509d45e` made `_is_reminder_day()` compare `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both the triage close reminder and the stable reminder depend on it, so neither was sent. The daily triage reminder doesn't use it, so it kept working.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`, where Monday is 0 on both sides.

**Test:** `tests/case/test_case_scheduled.py` checks a Monday, a Tuesday and a Sunday. It has not been run against the old code to confirm it fails there. The three cases pass with the fix.

**Timeline from the logs:** the image `main-81d8ae42`, which contains `c509d45e`, started on both the scheduler and web pods on 2025-08-13 at 16:40Z. The Monday before (2025-08-11) still sent reminders, and 2025-08-18 was the first Monday with none.

The `TypeError` on `case.triage_at` in `case_close_reminder` that I noted earlier is still there. It was logging before the deploy too, so it isn't what stopped the reminders, and I didn't touch it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18