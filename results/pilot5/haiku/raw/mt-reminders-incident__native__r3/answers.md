**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check in `src/dispatch/case/scheduled.py`. The helper it added is:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # scheduled.py:33
```

`isoweekday()` returns 1 for Monday (Mon=1…Sun=7), but `calendar.MONDAY` is 0 (I checked both in the sandbox). So `_is_reminder_day()` is always False, and the `q >= 1 and _is_reminder_day()` guards in `case_close_reminder` (line 49) and `case_stable_reminder` (line 95) never send. The old code was `date.today().isoweekday() == 1`, which was correct.

The daily triage reminder (`case_triage_reminder`) has no weekday check, so it keeps working. That matches the symptom.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. The scheduler and web pods started on it at 2025-08-13 16:40 UTC. `c509d45e` is an ancestor of `81d8ae42`, so the image contains the bug. The 08-12 scheduler pod (`xdp7k6gs2q`) was still on the older build, and its Monday 08-11 run sent close and stable reminders. The new pod (`mhtsgqwwx`) skipped them on Monday 08-18. Its traceback line numbers (47 and 55 in `case_close_reminder`) match the current file.

The git history was checked, but the deploy itself was inferred from the pod logs, not from a deploy record. I didn't change any code.

**Side issue, unrelated to the symptom:** `case_close_reminder` logs a `NoneType` error for every triage case where `triage_at` is null (every night from 07-28). The per-case `try/except` catches it, so it doesn't stop the run. `32fa810f` added the `stable_at` guard to the stable reminder but nothing equivalent for `triage_at`.

**Suggested fix (not applied):** compare with `date.today().weekday() == calendar.MONDAY`, or go back to `isoweekday() == 1`. Adding a test that runs the check on a Monday date would catch this kind of mistake.

----- next turn -----

The weekly reminders are fixed and there's a regression test for them. The change is not committed.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches again. The old `isoweekday()` value is 1-based, which is why the check never passed.
- **Regression test:** `tests/case/test_case_scheduled.py` has four cases. For a fixed Monday the close and stable reminders must send, and for a fixed Tuesday they must not. It swaps in a fake `date` and runs the undecorated task bodies on a stubbed case and project.
- **Verification:**
  - The new tests pass with the fix (4/4).
  - With the buggy line put back, the two Monday cases fail, so the test would have caught this.
  - `python -m pytest tests/case` passes (19/19).
  - I didn't run the full test suite.
  - `ruff` didn't produce output (I didn't confirm it's installed), so I haven't checked lint or formatting.

The side issue from before is still there: `case_close_reminder` logs a `NoneType` error for every triage case with no `triage_at`. I left it alone since it's outside this fix.

----- next turn -----

The close reminder no longer crashes on cases without `triage_at`. Those cases now count their weekly clock from `created_at`, and the test passes.

**Cause of the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`, and `triage_at` is NULL for some triage cases. Python raises `TypeError` on the subtraction, and the per-case `try/except` logs it. The job runs every evening, so the error repeats nightly.

I found two ways a case can end up with a NULL `triage_at`:
- The `triage_at` migration (`2022-08-01_391f7c3e6992`) added the column without backfilling existing rows. Cases from before then keep NULL unless something later sets it.
- `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py` sets `status = triage` directly, skipping the transition flow that stamps `triage_at`.

I can't see the production rows, so I haven't confirmed which path produced the NULLs in your data. The migration explanation is the more likely one, since the reopen button only acts on cases that were already closed.

**Fix** (`src/dispatch/case/scheduled.py`): the job now counts from `case.triage_at or case.created_at`. The stable reminder already has its own `stable_at` guard, and I didn't touch it.

**Test** (`tests/case/test_case_scheduled.py`): a new test on a Monday with two triage cases that have no `triage_at`. The case created 8 days ago gets the reminder, and the one created 2 days ago doesn't. With the fallback removed, the test fails, so it catches the bug.

`python -m pytest tests/case` passes (20/20). I didn't run the full suite.

I did not change the reopen button bypass. It's a second, separate source of cases without a `triage_at`. It would be a small change to run the triage transition flow there, if you want it.

----- next turn -----

## Recap: weekly reminders not sent after the 2025-08-13 deploy

**Symptom:** Since mid-August, assignees didn't get the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into a helper. The helper compared `date.today().isoweekday()`, which is 1-based (Monday = 1), against `calendar.MONDAY`, which is 0-based (Monday = 0). The comparison was never true, so both weekly reminders were suppressed. The daily triage reminder has no weekday check, so it was unaffected.

**Deploy:** Image `main-81d8ae42` started on the scheduler and web pods at 2025-08-13 16:40 UTC, and it contains `c509d45e`. The Monday 2025-08-11 run, before the deploy, still sent reminders. The Monday 2025-08-18 run did not. I inferred the deploy from pod logs; I did not check a deploy record.

**Fix (uncommitted):** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. A regression test in `tests/case/test_case_scheduled.py` fails on the old check and passes on the fix.

**Side issue, fixed (uncommitted):** `case_close_reminder` logged a `TypeError` every evening. It subtracted `case.triage_at` from `utcnow()`, and `triage_at` was NULL for some triage cases. The migration that added the column didn't backfill rows, and the Slack reopen button sets Triage without stamping `triage_at`. The job now counts from `created_at` when `triage_at` is missing, and a test covers that. I haven't confirmed which path produced the NULLs in production data.

**Not changed:** the reopen button in `src/dispatch/plugins/dispatch_slack/case/interactive.py` still bypasses the triage transition flow.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at