**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced the inline `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (I confirmed this by running it), but `isoweekday()` returns 1 to 7 with Monday as 1. The comparison can never be true, so `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both silently skip every case. The fix would be to compare against `date.today().weekday()` instead, or to use the literal `1`. The daily triage reminder (`case_triage_reminder`) never used the helper, which is why it kept working. I haven't changed any code.

**Deploy that shipped it:** the image `registry.example.com/dispatch:main-81d8ae42`, which the kubelet started on both the scheduler and web pods at 2025-08-13 16:40 UTC. The previous image, `main-b05613b5`, had been running since 2025-07-30 17:10 UTC. `c509d45e` is an ancestor of `81d8ae42` and not of `b05613b5`. The 81d8ae42 deploy carried about 28 commits, and this refactor was the only one touching the Monday logic.

**Log evidence:**
- "Case close reminder sent" lines appear on Monday 07-28 (4), 08-04 (6) and 08-11 (5).
- There are none on Monday 08-18, the first Monday after the deploy. The jobs still ran that day (the `case_close_reminder` and `case_stable_reminder` timer entries are in the log), and the daily triage reminder still went out.
- No exceptions point to this. The jobs run and exit cleanly, with nothing to alert on.

**Side notes:**
- Before the deploy, the logs show `unsupported operand type(s) for -: 'datetime' and 'NoneType'` errors in `case_stable_reminder` and `case_close_reminder` (07-28 onward). That is a separate, older problem, partly addressed by `32fa810f` (#6179). `case_close_reminder` still doesn't guard against a `None` `triage_at`.
- The refactor presumably had no test for the Monday gate.
- Reminders missed on 08-18, and any Mondays since, were not sent. The logs end 08-20, so I can't say whether the fix is deployed since then.

----- next turn -----

The Monday reminders are fixed, and the new regression test would have caught the bug. I ran only the new test file, not the full suite.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both use the 0-based numbering, so they agree on Monday. I added a comment explaining the numbering.

**Test:** `tests/case/test_case_scheduled.py` freezes the date and covers two things:
- `_is_reminder_day()` is true on Mondays (2025-08-11 and 2025-08-18) and false on the other days of that week.
- `case_close_reminder` and `case_stable_reminder` each send for a case that has been triaging or stable for 10 days only on a Monday, not on a Tuesday. It calls the registered scheduler tasks, unwrapping the decorators.

**Results:** with the fix, 12 tests pass. With the old code stashed, 4 fail: both Monday cases of `_is_reminder_day()` and both Monday sends. The Tuesday cases pass on the old code, as they should.

I haven't committed anything. Reminders missed on Mondays since 2025-08-18 won't be resent when this deploys. The next Monday after the deploy will send them again.

----- next turn -----

The nightly TypeError is fixed. Cases with no `triage_at` now count from `created_at`, so they get their weekly reminder. The new test file passes with 15 tests. I haven't run the full suite or committed anything.

**Cause:** in `src/dispatch/case/scheduled.py`, `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is a nullable column, and it is only filled in when a case moves into triage (`case_triage_status_flow` in `flows.py`). Cases created directly in triage, and older cases, never get one. Every evening at 18:00 each of those cases raised `TypeError: unsupported operand ... 'datetime' and 'NoneType'`. The per-case `try/except` caught it and logged it, so the job carried on but those cases never got a reminder. The log shows it from 07-28, well before the Monday-check regression.

**Fix:** the job now uses `case.triage_at or case.created_at` as the starting point, with a comment explaining why.

**Tests:** I added two tests to `tests/case/test_case_scheduled.py`:
- A case with no `triage_at` that is 10 days old gets the reminder on a Monday and not on a Tuesday, and nothing is logged as an exception.
- A case with no `triage_at` that is only 2 days old gets no reminder, even on a Monday.

**Check against the old code:** I stashed `scheduled.py` to check, which removed both fixes at once. That run had 6 failures, including the new fallback test.

`case_stable_reminder` has the same shape with `stable_at`. It already skips cases that have no `stable_at` (from `32fa810f`) and does not fall back to `created_at`, so stable cases with no `stable_at` still get no reminder. You only asked about the close reminder, so I left that alone. Say if you want the same fallback there.

----- next turn -----

**Recap**

- **Weekday bug:** commit `c509d45e` (2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compares `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The comparison is never true, so the weekly close reminders for long-running triage cases and stable cases stopped going out. The daily triage reminder doesn't use the helper, so it kept working.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` went onto the scheduler and web pods at 2025-08-13 16:40 UTC. It replaced `main-b05613b5`, which doesn't contain `c509d45e`.
- **First missed reminders:** Monday 2025-08-18. Reminders were sent on 07-28, 08-04 and 08-11, none on 08-18, even though the jobs ran. The 08-11 reminders went out before the deploy.
- **Fix:** `_is_reminder_day()` now compares `weekday()` with `calendar.MONDAY`. A regression test covers the helper and both reminder jobs.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is nullable. It is only set when a case transitions into triage, so cases created directly in triage have none. The job now falls back to `created_at`, and tests cover that. The error predates the weekday bug and appears in the logs from 07-28.
- **Not changed:** `case_stable_reminder` skips cases with no `stable_at` instead of falling back to `created_at`.
- **Status:** the changes are uncommitted. I ran only the new test file (15 passed), not the full suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at