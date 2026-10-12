**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. The old code compared `isoweekday()` to `1`, which is Monday. The refactor moved that check into `_is_reminder_day()` and compares against `calendar.MONDAY`. In Python `calendar.MONDAY` is `0` (weeks start on Monday, indexed from 0), so the comparison is never true. I confirmed this with `python3 -I`: `calendar.MONDAY == 0`, while `date(2025, 8, 18).isoweekday() == 1`.

The bad line is in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # always False
```

It is used by `case_close_reminder` (line 49) and `case_stable_reminder` (line 95). Both now skip every day, which is why the weekly stable and triage-close reminders stopped while the daily triage reminders (`case_triage_reminder`, which has no weekday check) kept going.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which is commit `81d8ae42` (2025-08-12, "fix(case): exclude resolved_by in update (#6183)"). `c509d45e` is an ancestor of it, and it is the first commit in the line that touches the check. The scheduler pod started on that image at 2025-08-13 16:40 UTC (`scheduler-mhtsgqwwx-q5q2n`, per `scheduler.log`). The earlier scheduler pod ran `main-b05613b5` and still sent reminders on Monday 2025-08-11 (5 close reminders at 18:00 that day).

**Confirmation from the logs:**
- Monday 2025-08-11 18:00: close reminders sent (old image).
- Monday 2025-08-18 18:00: zero close reminders sent. Triage reminders went out (1 sent), so the daily path still works.
- Reminder runs on other days through 2025-08-20 are unaffected in the sense that they are not Mondays.

**Fix I'd suggest (not applied, per your instruction):** restore the weekday comparison to `== 1`, or better, compare against `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based, so the constant then matches). Also add a test for `_is_reminder_day`, since nothing exercises it and that is how this shipped.

**Separate issue I noticed, not the cause:** `case_close_reminder` also throws `TypeError: ... 'NoneType'` at `scheduled.py:47` (`case.triage_at` is `None`) on every daily run. The per-case `try/except` contains it, so other cases still get reminders, but the same kind of None-guard that `32fa810f` added for `stable_at` is missing for `triage_at`.

----- next turn -----

The Monday reminder bug is fixed, and a regression test covers it. I did not commit.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Before, it compared `isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so it never matched.

**The regression test** (`tests/case/test_case_scheduled.py`, new file):
- `test_is_reminder_day` checks every day of the week with a frozen date, so Monday must be true and the other six days false.
- `test_weekly_case_reminders_only_send_on_monday` runs the real stable and triage reminder tasks against the database for a case 8 days old. A Tuesday run must send nothing, and a Monday run must send the reminder.

**Verification:**
- With the fix, the 9 new tests pass.
- With the old line restored, 3 of them fail: the Monday case in `test_is_reminder_day` and both task-level Monday tests. So the tests catch this bug.
- The full suite gives 8 failed, 368 passed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). They fail the same way on the original code, so they predate this change and are unrelated to it.

I did not address the separate `triage_at is None` crash in `case_close_reminder`, since you asked only for the Monday fix. The fix is a one-line guard like the one already used for `stable_at`, if you want it.

----- next turn -----

The evening `TypeError` is fixed. Cases with no `triage_at` now count from `created_at`, and a regression test covers it. I did not commit.

**What causes it:** `triage_at` is only written by the triage transition flow (`case_triage_status_flow`, `src/dispatch/case/flows.py:592`). Some cases reach triage status without that flow running, so the column stays NULL. The clearest path is the Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`), which sets `case.status = CaseStatus.triage` directly. A case closed straight from New and then reopened that way has no `triage_at`, and the close reminder subtracts `None` from a datetime. Dispatcher arms for "Any → Triage" also log a warning and skip setting it.

I could not check which case IDs are affected: the logs don't include them, and I have no production database access. The reopen-button path is my best explanation, not a confirmed case.

**The fix** (`src/dispatch/case/scheduled.py:47-50`): the job now computes `triage_start = case.triage_at or case.created_at` and counts from that. `created_at` is set on every case. The per-case `try/except` is unchanged.

**Tests** (`tests/case/test_case_scheduled.py`): added a parametrized test covering a missing `triage_at` with an old `created_at` (sent), a missing `triage_at` with a recent `created_at` (not sent), and a present `triage_at` taking precedence over `created_at`. The missing-`triage_at` case fails on the old code and passes with the fix.

**Verification:** the scheduled-reminder tests pass (13). The full suite gives 8 failed, 372 passed, 4 skipped. The same 8 failures (AI service, one database test, one entity test) also happen on the original code, so they are pre-existing and unrelated.

**Not changed, your call:**
- The root cause is still there: the reopen button skips the transition flow. The fix could make it call `case_triage_status_flow`, which would also stop new NULL `triage_at` rows.
- Stable reminders still skip cases with no `stable_at` rather than falling back to `created_at`. You only asked about the close reminder, so I left that alone.

----- next turn -----

## Recap

**Weekly reminders stopped because of one commit.** Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The old code compared `isoweekday()` (Monday = 1) to 1. The new code compared it to `calendar.MONDAY`, which is 0 in Python, so the check was never true. Weekly close and stable reminders were skipped on every day; daily triage reminders have no weekday check and kept going.

**Deploy:** the scheduler pod started on image `main-81d8ae42` (commit `81d8ae42`, which contains `c509d45e`) at 2025-08-13 16:40 UTC. The previous scheduler image, `main-b05613b5`, still sent reminders on Monday 2025-08-11 (5 close reminders). The next Monday, 2025-08-18, sent none, while triage reminders for that day went out.

**Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`. `triage_at` is only set by the triage transition flow, so cases that reach triage without it (the Slack reopen button sets the status directly, for example) have it NULL, and the job raised `TypeError` each evening. The per-case `try/except` kept other cases going. The job now counts from `created_at` when `triage_at` is missing.

**Fixes and tests:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday()`, and `case_close_reminder` falls back to `created_at`.
- `tests/case/test_case_scheduled.py` (new): tests for the weekday check across a week, the Monday-only behaviour of both weekly jobs, and the `created_at` fallback. I confirmed the Monday and fallback tests fail on the old code.
- Full suite: 8 failed, 372 passed, 4 skipped. The 8 failures (AI service, one database test, one entity test) also fail on the original code, so they predate this work.

**Open items:**
- The reopen button path that leaves `triage_at` NULL still exists. Routing it through the triage flow would stop new NULL rows.
- Stable reminders still skip cases with no `stable_at` rather than falling back to `created_at`.
- No changes are committed.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```