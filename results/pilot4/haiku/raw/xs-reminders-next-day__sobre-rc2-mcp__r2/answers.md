**Root cause:** commit `c509d45e` broke the Monday check. It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which compares against `calendar.MONDAY`. Those two use different numbering:

- `isoweekday()` returns Monday = 1.
- `calendar.MONDAY` is 0, because `calendar` numbers Monday as 0.

So `_is_reminder_day()` is False every day, and `case_close_reminder` and `case_stable_reminder` never send. I confirmed this by running it: on 2025-08-11 (a Monday), `isoweekday()` is 1 and `isoweekday() == calendar.MONDAY` is False.

The daily `case_triage_reminder` (new cases and Security Event triage) doesn't use the helper, which is why those reminders still arrive.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the `web` and `scheduler` pods at 2025-08-13T16:40 UTC. The previous image, `main-b05613b5`, started on 2025-07-30 and doesn't contain the commit. `c509d45e` is an ancestor of `81d8ae42`; the commits in between are `7c446bd6` and `81d8ae42` itself. The image tag matches the commit hash, so the mapping is direct.

**Log evidence:**
- The last successful weekly sends were on Monday 2025-08-11 (`Case close reminder sent to …`, 5 that day). The first Monday after the deploy, 2025-08-18, has no sends.
- Both `case_close_reminder` and `case_stable_reminder` log their executions on 08-18 and 08-19 without sending anything.
- The `stable_at` None errors stop after 2025-08-12, which is consistent with the new image (`32fa810f`, the `stable_at` guard, shipped in the same deploy) only landing on 08-13.
- `api.log` has no reminder entries, so the scheduler is the only relevant source.

**Not changed:** no code was edited. A likely fix is to compare against `date.today().weekday() == calendar.MONDAY` (since `weekday()` also uses Monday = 0), or to compare `isoweekday()` with `1`. I'd also add a test that pins `_is_reminder_day()` to a known Monday. Want me to make that change?

----- next turn -----

The weekly Monday reminders stopped because `_is_reminder_day()` compared `isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). It never matched, so the Monday check was always false.

- **Cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the check into `_is_reminder_day()`. The original code compared against the literal `1`, which was correct.
- **Shipped:** deployed as `main-81d8ae42` on 2025-08-13 16:40 UTC, on both the scheduler and the web containers. The scheduler was on `main-b05613b5` before that, which doesn't include the refactor.
- **Evidence:** case close reminders went out on Mondays 2025-07-28, 08-04 and 08-11. On 2025-08-18 both `case_close_reminder` and `case_stable_reminder` ran at 18:00 and sent nothing.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` use the same 0-based numbering.

**Regression test:** `tests/case/test_case_scheduled.py` freezes "today" to a Monday, a Tuesday and a Sunday, and checks `_is_reminder_day()` for each. With the old code the Monday case fails. With the fix all three pass, and `python -m pytest tests/case` passes (18 tests).

Not done:
- I didn't commit or deploy anything.
- The logs end on 2025-08-20, so I can't confirm the state of later Mondays. The bug would have skipped them too.
- Unrelated, not fixed: every day the scheduler logs an `unsupported operand type(s) ... NoneType` error for cases with no `triage_at` or `stable_at`. The per-case `try` catches it, so it doesn't stop the other reminders, but it adds noise every run.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18