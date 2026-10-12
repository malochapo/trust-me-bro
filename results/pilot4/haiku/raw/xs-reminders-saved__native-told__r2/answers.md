**Root cause:** the Monday gate in `_is_reminder_day()` can never be true. It lives in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns Monday as `1`, but `calendar.MONDAY` is `0`. So the check is always false, and `case_close_reminder` and `case_stable_reminder` never send their weekly reminders. The daily triage reminder lives in `case_triage_reminder`, which has no weekday gate, so it keeps working.

**Commit that introduced it:** `c509d45e` "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). It replaced the original literal `date.today().isoweekday() == 1` with `_is_reminder_day()` and the `calendar.MONDAY` constant, which uses a different numbering.

**Deploy that shipped it:** `81d8ae42` "fix(case): exclude resolved_by in update (#6183)" (David Whittaker, 2025-08-12). It contains `c509d45e`, and the image `registry.example.com/dispatch:main-81d8ae42` started on the scheduler and web pods at 2025-08-13T16:40Z.

**Evidence from the logs:**
- Monday 2025-08-04 and Monday 2025-08-11 both logged "Case close reminder sent" entries, which were before the deploy.
- Monday 2025-08-18 logged only incident close reminders and no case close reminders.
- The triage reminders kept sending daily, as you described.

**Related issue in the same deploy:** `case_close_reminder` has no `triage_at is None` guard. Only the stable path got one, in `32fa810f`. Since 08-13 it logs a `TypeError` for every triage case without a `triage_at` each day. The per-case `try/except` contains it, so it does not block other reminders, but it is noise and should be fixed alongside.

No code has been changed. I saved these findings to the memory directory for later sessions.

----- next turn -----

I saved the findings to the memory file `weekly-case-reminder-monday-bug.md`, which is indexed in `MEMORY.md`. Tomorrow's session can pick them up from there.

The saved state:
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compares `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the weekly Monday gate never passes.
- **Introduced by:** `c509d45e` (refactor, 2025-08-12).
- **Shipped by:** `81d8ae42` (fix, 2025-08-12), deployed as `main-81d8ae42` on 2025-08-13 at 16:40Z.
- **Open items:** fix the Monday gate, add a `triage_at is None` guard to `case_close_reminder`, and add a test for the gate.
- **Status:** no code has been changed and no fix has been applied.

----- next turn -----

The Monday reminder bug is fixed and covered by a regression test. The fix is in the working tree and not committed.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check was never true. Commit c509d45e introduced it when it moved the check into a shared helper. The image `main-81d8ae42` shipped it on 2025-08-13 at 16:40Z.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`, which matches the constant the code already uses.

**Regression test:** `tests/case/test_case_scheduled.py` pins `date.today()` to each day of one week and asserts that only Monday passes. It fails on the old code on Monday and passes after the fix. `python -m pytest tests/case` passes (22 tests). I did not run the full suite.

**Logs:** Close reminders went out on Mondays 2025-08-04 and 2025-08-11. On 2025-08-18 only triage reminders went out, so that is the first missed Monday.

**Not done:** The 2025-08-18 scheduler log also shows a `TypeError` in `case_close_reminder`, because some triage cases have no `triage_at` and the subtraction runs before the weekday gate. It is caught per case, so it does not block other sends, but it repeats daily. I left it alone because it's a separate change; adding a `triage_at is None` guard, as `case_stable_reminder` already has for `stable_at`, would fix it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18