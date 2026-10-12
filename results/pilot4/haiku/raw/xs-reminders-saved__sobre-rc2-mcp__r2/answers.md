**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares two different Monday numbering schemes:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday through 7 for Sunday, but `calendar.MONDAY` is 0. The comparison can never be true, so the weekly gate is never open. Both `case_close_reminder` (triage) and `case_stable_reminder` (stable) call it, so both weekly reminders stopped. The daily `case_triage_reminder` does not call this helper, which is why the daily triage reminders kept arriving.

**Introducing commit:** `c509d45e` (Jordan Lee, 2025-08-12 14:05 -0700, "refactor(case): share the weekly reminder check"). It replaced the inline `date.today().isoweekday() == 1` with the helper and changed the literal `1` to `calendar.MONDAY`. That swap is the bug. The commit is described as a refactor but changed behavior.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42` (commit `81d8ae42`, "fix(case): exclude resolved_by in update (#6183)"). `c509d45e` is an ancestor of it, and it is not in the previous image `main-b05613b5`. The logs show both the scheduler and web pods starting on that image at 2025-08-13 16:40Z (`scheduler.log:18851`, `api.log:13201`). This is the only rollout between the last working Monday and the first broken one.

**Evidence from the logs:**
- Mon 2025-08-11 18:00Z: close reminders sent to several assignees (`scheduler.log` ~16799–16808). This ran before `c509d45e` was deployed.
- Mon 2025-08-18 18:00Z: no "Case close reminder sent" lines, while the daily "Case triage reminder sent" lines appear (`scheduler.log:25281`).

**Two things I noticed but did not treat as the root cause:**
- `case_close_reminder` still logs `unsupported operand type(s)... 'NoneType'` on every run at `scheduled.py:47` (`triage_at` is None). Those cases are skipped by the weekly reminder. This is a separate, pre-existing issue. The same error in `case_stable_reminder` was fixed by `32fa810f` on 08-11, which is in the same image.
- The scheduler log's ERROR lines for `case_stable_reminder` at line 101 before 08-11 match the code before `32fa810f`, so they are not evidence of a regression.

**Suggested fix (not applied, as you asked):** use the 0-based weekday, `date.today().weekday() == calendar.MONDAY`, or compare against `1` to match the original code. A test that pins `_is_reminder_day` to a known Monday would catch this.

I made no code changes.

----- next turn -----

I saved the findings to a project memory note and added an index entry, so a new session can pick them up.

- **Note:** `memory/weekly-case-reminder-regression.md`. It records the root cause (`isoweekday()` compared with `calendar.MONDAY`), the offending commit `c509d45e`, the shipping image `main-81d8ae42` (started 2025-08-13 16:40Z), the log evidence, and the suggested fix.
- **Index:** `memory/MEMORY.md` has a one-line pointer to it. The memory directory was empty before this, so nothing existing was updated.

The fix is not applied and no code was changed. The note also flags the separate `triage_at` None error in `case_close_reminder`, which is not fixed.

----- next turn -----

The weekly Monday reminders are fixed, and a regression test covers the bug.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent. The daily triage reminder doesn't use this helper, which is why it kept working.

**Logs confirm this:**
- Monday 2025-08-11 sent close reminders.
- Monday 2025-08-18 sent none, while `case_stable_reminder` and the daily triage reminder kept running.
- The 2025-08-13 image `main-81d8ae42` is the first to include the bug. The previous image `main-b05613b5` (2025-07-30) does not.

**Changes:**
- `src/dispatch/case/scheduled.py`: `date.today().isoweekday()` → `date.today().weekday()`.
- `tests/case/test_case_scheduled.py` (new): parametrized test of `_is_reminder_day()` with two known Mondays and three non-Monday days. With the old code, both Monday cases fail. With the fix, all five pass.
- I updated the memory note, which still said the fix was unapplied.

**Tests:** `python -m pytest tests/case` passes (20 tests). I did not run the full suite.

**Not fixed:** `case_close_reminder` logs a `'datetime' - 'NoneType'` error on every run at `scheduled.py:47`, because `triage_at` can be None. Those cases are skipped. Fixing it would be a separate change.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18