**Root cause:** `_is_reminder_day()` compares the wrong weekday constant. It returns `date.today().isoweekday() == calendar.MONDAY`, but `calendar.MONDAY` is `0` (Monday is 0 in `calendar`) while `isoweekday()` returns `1` for Monday. The check is never true, so the weekly close and stable reminders never send. The daily triage reminder doesn't use this check, which is why it still goes out.

**Where it came from:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()` and used `calendar.MONDAY` in place of the literal `1`. The old literal was correct, so the refactor changed behaviour. `src/dispatch/case/scheduled.py:33`.

**Deploy that shipped it:** scheduler image `registry.example.com/dispatch:main-81d8ae42`, started by kubelet at 2025-08-13T16:40:06Z (`scheduler.log:18851`). That image is commit `81d8ae42` (#6183, "exclude resolved_by in update"), and `c509d45e` is an ancestor of it. The previous image, `main-b05613b5`, started on 2025-07-30 and doesn't contain the refactor.

**Confirmation from the logs:**
- Monday 2025-08-11 ran on the old image and sent the weekly close and stable reminders (r.patel, s.lindqvist, a.chen, m.okafor, k.tanaka).
- Monday 2025-08-18 was the first Monday on the new image. The scheduler sent no case close or stable reminders. The triage reminder and the incident close reminder still went out.

**Related problems, not the cause:** the logs show other errors on the same daily runs. `case_close_reminder` (`scheduled.py:47`) calls `datetime.utcnow() - case.triage_at` with no `None` guard, so triage cases with no `triage_at` raise on every run. The stable path has the same kind of error (`case.stable_at` is `None`) in the logs through 08-20. Commit `32fa810f` (#6179) added a `stable_at` guard, but the traceback lines still match the unguarded code, so I can't confirm from the logs that the guard reached production. Each per-case failure is caught by `try/except`, so these don't stop the other cases, but they cost one error per affected case per day.

I haven't changed any code. The fix is to compare against `1` or `calendar.MONDAY` after converting it, e.g. `date.today().weekday() == calendar.MONDAY`, which is the 0-based form. The current `incident/scheduled.py:229` still uses the literal `1`, so it's unaffected. A test for `_is_reminder_day()` would have caught this.

----- next turn -----

The weekly Monday reminders were never sent after the Aug 13 deploy. The fix is one line and the regression test is in place.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). The check was never true, so the case close and stable reminders were skipped every day. Commit `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") moved the old `isoweekday() == 1` check into this helper and introduced the mismatch. It shipped in `main-81d8ae42`, which the scheduler started on 2025-08-13. The `main-b05613b5` image from before that was not affected. The last case close reminders went out on Monday 2025-08-11, and none went out on 2025-08-18.

**Fix:** `date.today().weekday() == calendar.MONDAY`. I did not commit it.

**Regression test:** `tests/case/test_case_scheduled.py` (new) pins the date to Monday 2025-08-18 and to Tuesday, and runs the registered case close and stable reminder tasks against a case that has been in triage or stable for 8 days. On the buggy line, 4 of the 6 tests fail. With the fix, all 6 pass. `python -m pytest tests/case` gives 21 passed, and ruff passes on both files.

**Not fixed:** `case_close_reminder` has no `triage_at is None` guard, although `case_stable_reminder` has one. Cases with no `triage_at` raise `TypeError` at `scheduled.py:47` on every daily run. The per-case `try/except` catches it, so other cases still get reminders, but those cases never do. This is a separate bug and I left it alone. Adding the same guard would fix it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18