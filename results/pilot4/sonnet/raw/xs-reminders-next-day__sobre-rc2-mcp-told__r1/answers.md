The root cause is a one-line constant mix-up in commit `c509d45e`. It shipped to production in the deploy of image `main-81d8ae42` on 2025-08-13 at 16:40Z. I changed no code.

**Root cause**
- `c509d45e` is "refactor(case): share the weekly reminder check", by Jordan Lee, committed 2025-08-12.
- It replaced the inline `date.today().isoweekday() == 1` in `case_close_reminder` and `case_stable_reminder` with a shared helper (`src/dispatch/case/scheduled.py:31`):
  ```python
  return date.today().isoweekday() == calendar.MONDAY
  ```
- `isoweekday()` numbers Monday as 1 and Sunday as 7. `calendar.MONDAY` is 0, because the `calendar` module counts from Monday = 0. I confirmed this by running it: `calendar.MONDAY` is 0, and 2025-08-18 (a Monday) has `isoweekday()` 1.
- So the check never matches on any day, and the weekly reminders for triage and stable cases are never sent. The daily triage reminder (`case_triage_reminder`) never used this check, which is why it kept working.

**Evidence in the logs**
- On Monday 2025-08-04 and 2025-08-11, at 18:00Z, the old pod (`scheduler-xdp7k6gs2q-w6cj7`) logged several "Case close reminder sent to …" lines.
- On Monday 2025-08-18, at 18:00Z, the new pod logged none. The only reminder-related output was an incident close reminder.

**The deploy**
- `scheduler.log` and `api.log` both show the scheduler and web containers restarting on 2025-08-13 at 16:40Z, with image `registry.example.com/dispatch:main-81d8ae42`.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", from 2025-08-12. `git merge-base --is-ancestor` confirms it contains `c509d45e`.
- The previous image, `main-b05613b5` (2025-07-29), does not contain `c509d45e`.
- The first Monday after the deploy was 2025-08-18, which matches the reported start of the problem.
- That deploy also carried 24 other commits since `b05613b5`. I only inspected `c509d45e`, because it alone changes this check.

**Separate issues I noticed**
- **Missing `triage_at`:** On 2025-08-18, `case_close_reminder` logged "unsupported operand … NoneType" at `scheduled.py:55`, so a triage case has no `triage_at`. The per-case `try/except` only logs it, so other cases still get processed. Once the Monday check is fixed, that case will be skipped silently, and it needs a guard like the one `case_stable_reminder` already has for `stable_at`.
- **Stable-case guard:** `case_stable_reminder` hit the same `stable_at` None error daily until the guard from `32fa810f` (2025-08-11) landed. That guard is unrelated to the missing Monday reminders.
- **DB outage:** The scheduler logged a database "Connection refused" error on 2025-08-15, unrelated to this.

**Suggested fix (not applied)**
- Use `calendar.MONDAY + 1`, or `date.today().weekday() == calendar.MONDAY`, or `== 1` as before.
- A small test that mocks a Monday date would have caught this.

----- next turn -----

Weekly close reminders for triage and stable cases work again. The new test passes with the fix and fails on the Monday case without it.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check was never true and no Monday reminder was sent. Commit c509d45e (2025-08-12) introduced it when it replaced the inline `isoweekday() == 1` check with a shared helper.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`. Both `weekday()` and `calendar.MONDAY` use 0 for Monday.

**Test:** `tests/case/test_case_scheduled.py` checks that a Monday returns true and that Tuesday, Saturday and Sunday return false. I did not run the rest of the suite.

**Logs:**
- Reminders went out on 2025-07-28, 08-04 and 08-11.
- The first deploy after the bad commit was image `main-81d8ae42` on 2025-08-13, and 81d8ae42 descends from c509d45e.
- The 08-18 scheduler run logged no "Case close reminder sent" lines, while the triage and incident reminders still ran.

I left one separate problem alone. `case_close_reminder` also logs `datetime - NoneType` errors on many days, including before the regression, because some triage cases have a null `triage_at`. That error is caught per case, but it skips those cases, so you may want a follow-up fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18