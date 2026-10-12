**Root cause:** the weekday check in `_is_reminder_day()` can never be true, so the weekly close and stable reminders never send. The daily triage reminder has no weekday gate, which is why it still arrives.

**Where:** `src/dispatch/case/scheduled.py:31-33`

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's calendar counts Monday as 0). I confirmed `calendar.MONDAY == 0` in this environment. The helper therefore always returns False, and both `case_close_reminder` (line 49) and `case_stable_reminder` (line 95) skip the send. The helper replaced the literal `== 1` in the original code.

**Commit that introduced it:** `c509d45e` by Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check." Before this, the check was `date.today().isoweekday() == 1`, which was correct.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13T16:40:06Z (`scheduler.log:18851`). The image tag is the commit `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)"), and `c509d45e` is an ancestor of it. The previous image, `main-b05613b5` (2025-07-30), predates the refactor. The log shows no other deploy between those two.

**Corroborating evidence:**
- The stable-reminder crash (`case_stable_reminder:101`, `None` `stable_at`) appears daily through 2025-08-12 and stops after the 08-13 deploy. That fits the same deploy carrying the `stable_at` guard from `32fa810f` (2025-08-11), so the stable crash was fixed in that build and the Monday check broke in it.
- The logs don't show any reminder sends, so I can't confirm from them that no Monday reminder went out after 08-13. The Monday 2025-08-18 run only shows per-case errors.

**Separate issue I noticed, not the cause:** `case_close_reminder` logs a `None` `triage_at` error on every daily run (`scheduler.log:26296`, 08-19 and 08-20, line 47 in the log trace). The per-case `try/except` keeps the job running, but cases with no `triage_at` never get a close reminder. This is worth a follow-up ticket.

**Suggested fix (not applied, per your instruction):** use the same convention as `.weekday()`, i.e. `return date.today().weekday() == calendar.MONDAY`, or compare to `1` against `isoweekday()`. I'd also add a test that pins a Monday date so this can't regress silently. Do you want me to make that change?

----- next turn -----

The weekly reminder check is fixed and a regression test is in place. The case test directory passes (22 tests), and the new test fails on the old code.

**The fix** is in `src/dispatch/case/scheduled.py:33`:

```python
return date.today().weekday() == calendar.MONDAY
```

The old code compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0). `weekday()` is 0-based like `calendar.MONDAY`, so the two now agree.

**The regression test** is in `tests/case/test_scheduled.py`. It parametrizes `_is_reminder_day()` over a Monday and the six other days of one week, with `date.today()` patched to a fixed date. Against the old code, the Monday case fails (`assert False is True`) and the other six pass. Against the fix, all seven pass.

Things to know:
- I ran `python -m pytest tests/case`, not the full suite. I didn't run `ruff` because it isn't installed in this environment, so formatting is unchecked.
- The test covers the helper, not the full reminder jobs. A test that drives `case_close_reminder` and `case_stable_reminder` end to end would be more thorough, but the decorator stack makes that more setup. I can add it if you want it.
- I did not touch the separate `case_close_reminder` issue where cases with no `triage_at` raise an error on every run.
- Nothing is committed.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, so those cases get their weekly reminder. `tests/case` passes (24 tests), including two new job-level tests.

**Cause of the TypeError.** `case_close_reminder` does `datetime.utcnow() - case.triage_at`, and `triage_at` is NULL on at least one triage case. The per-case `try/except` catches the error, so the job keeps going, but that case never gets a reminder. The errors start 2025-08-13 and occur once per day, which suggests one case. The logs don't include a case ID, so I can't confirm which case it is.

Two things can leave `triage_at` NULL:
- **Older cases.** `triage_at` was added in 2022 (`391f7c3e6992`) with no backfill, so cases created before that have NULL.
- **Reopen button.** `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427` sets `case.status = CaseStatus.triage` directly. That skips `case_triage_status_flow`, which is the only place `triage_at` gets set. Any case that was closed without ever being triaged and then reopened would end up with NULL `triage_at`. I didn't change this code, so it can still produce new NULLs.

**The fix** is in `src/dispatch/case/scheduled.py:47-49`:

```python
start = case.triage_at or case.created_at
span = datetime.utcnow() - start
```

**Tests** are in `tests/case/test_scheduled.py`. They run the job's undecorated function against the test session, with `send_case_close_reminder` stubbed:
- A triage case with no `triage_at`, created 10 days ago, gets the reminder.
- The same case created 3 days ago does not.

I didn't run the new tests against the old code. The old code would hit the TypeError, which is caught and skipped, so the 10-day case would not be sent and the first test would fail.

Decisions and gaps:
- The stable reminder still skips cases with no `stable_at` instead of falling back. You only asked about the close reminder, so I left it alone. The same fallback would work there if you want it.
- I haven't fixed the reopen path. It's a one-line change, but it changes case flow, so it's your call. I'd recommend routing it through the triage flow.
- The working tree has the weekday fix from before plus this change, and nothing is committed.

----- next turn -----

## Recap

**Incident:** Since the 2025-08-13 deploy, assignees have not received the weekly Monday reminders for long-running triage and stable cases. The daily triage reminder was unaffected because it has no weekday gate.

**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was always false, so both weekly jobs skipped every send. The check was written as `== 1` before commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"), which replaced the literal with `calendar.MONDAY`.

**Deploy:** Image `registry.example.com/dispatch:main-81d8ae42` started on the scheduler at 2025-08-13 16:40 UTC. That commit contains `c509d45e`. The previous image, `main-b05613b5`, predates the refactor.

**Fix:** `weekday()` replaces `isoweekday()`, so the comparison uses the same 0-based numbering as `calendar.MONDAY`. Regression test: `tests/case/test_scheduled.py::test_is_reminder_day` covers all seven days of a week and fails on the old code for Monday.

**Secondary issue:** `case_close_reminder` logged a TypeError each evening from 2025-08-13 onward. The job subtracted `case.triage_at` from the current time, and `triage_at` was NULL for at least one triage case. The per-case `try/except` kept the job running, but that case never got a close reminder. The fix counts from `case.created_at` when `triage_at` is missing. Tests: `test_case_close_reminder_without_triage_at` covers an old case with no `triage_at` (sent) and a recent one (not sent).

**Open items:**
- **Cause of the NULL `triage_at` is not confirmed.** The logs don't include a case ID. Two plausible sources: cases from before `triage_at` was added in 2022 with no backfill, and the Slack reopen button (`reopen_button_click`, `plugins/dispatch_slack/case/interactive.py:1427`), which sets `status = triage` without going through the triage flow. The reopen path is not fixed.
- **First missed Monday is inferred, not observed.** The logs contain no send records. I took the first Monday after the 08-13 deploy from the deploy time and the code.
- **Uncommitted.** The weekday fix, the `created_at` fallback, and the new tests are in the working tree only.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```