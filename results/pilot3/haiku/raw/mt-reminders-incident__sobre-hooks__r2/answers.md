**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", by Jordan Lee, 2025-08-12) moved the Monday test into `_is_reminder_day()` and compares the wrong numbering:

```python
# src/dispatch/case/scheduled.py
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's `weekday()` numbering). I checked both in the sandbox: `calendar.MONDAY = 0`, `date(2025,8,18).isoweekday() = 1`. So `_is_reminder_day()` is always False, and the guard `q >= 1 and _is_reminder_day()` in `case_close_reminder` and `case_stable_reminder` never passes. The old code used `== 1`, which was correct. The refactor looked behavior-preserving but wasn't.

This explains the symptoms:
- **Weekly close/stable reminders stop:** both jobs gate sends on `_is_reminder_day()`.
- **Daily triage reminders continue:** `case_triage_reminder` has no weekday check, so it isn't affected.
- **No config change:** the code change alone did it.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started 2025-08-13 16:40 UTC (`api.log` and `scheduler.log`, pod `scheduler-mhtsgqwwx-q5q2n`). `c509d45e` is an ancestor of `81d8ae42` and not of the previous image `main-b05613b5` (deployed 2025-07-30). Those are the only two rollout markers in the window. The first Monday under the new image was 2025-08-18, and that run logged no stable or close reminder sends. Before that, the logs don't show reminder sends explicitly, so I can't confirm from logs that the 08-04 and 08-11 Mondays sent. The code logic says they did.

**Unrelated noise (not the cause):** `scheduler.log` also has a steady stream of `TypeError: ... datetime - NoneType` from `case_stable_reminder` (line 93 in the installed package) and `case_close_reminder` (line 47). These come from cases with a null `stable_at` or `triage_at`. The per-case `try/except` catches them, so other cases still get processed. `32fa810f` ("not all cases have a stable_at date") is supposed to address the stable one, but the errors continue after the 08-13 deploy. That's a separate issue worth checking.

No code has been changed.

**Suggested fix (not applied):** make the weekday check use the same numbering as `calendar.MONDAY`, e.g. `return date.today().weekday() == calendar.MONDAY`, or revert to `isoweekday() == 1`. Add a unit test that pins a known Monday, so this can't regress silently.

----- next turn -----

The fix is in and the regression test is added. I haven't committed anything.

**The fix:** `src/dispatch/case/scheduled.py:33` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches again. The old `isoweekday()` is 1-based and compared against `calendar.MONDAY == 0`, which never matched.

**The regression test:** `tests/case/test_case_scheduled.py` pins "today" to each day of one week and asserts `_is_reminder_day()` is True only on Monday. I ran it against both versions:
- With the buggy `isoweekday()` line, the Monday case fails and the other six pass.
- With the fix, all seven pass.

The test checks the helper directly, not the full scheduled jobs. Those are wrapped by the task decorators and need a database session and a project context, so I kept the test small. If you want end-to-end coverage of `case_close_reminder` and `case_stable_reminder`, I can add that next.

**Full suite:** `python -m pytest tests` gives 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). I stashed the fix and reran those files: the same 8 fail without it, so they predate this change. The AI ones fail because tiktoken tries to download its encoding from the internet, and this sandbox has no network access. I did not investigate the other two.

----- next turn -----

The close-reminder `TypeError` is fixed. A triage case with no `triage_at` now counts from `created_at`, and it gets its weekly reminder. Nothing is committed.

**Cause:** `triage_at` is only written in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). The Slack reopen button handler, `reopen_button_click` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`), sets `case.status = CaseStatus.triage` directly and never runs the transition dispatcher. A case reopened into Triage therefore has `triage_at` NULL. Every evening `datetime.utcnow() - None` raises. The per-case `try/except` catches it, so the other cases still get processed. The stack trace shows the failing line but not which case, and the logs don't record case IDs. So the reopen path is the most likely source, but I haven't confirmed it against production data. To confirm, query for cases with status Triage and `triage_at` NULL.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`):
```python
# cases can reach triage without triage_at, so count from when the case was created
start = case.triage_at or case.created_at
span = datetime.utcnow() - start
```

**Tests** (`tests/case/test_case_scheduled.py`), which call the real job through the scheduler registry:
- Triage case with `triage_at` NULL, created 8 days ago, on a Monday: sends a reminder. This fails on the old line and passes with the fix.
- Same case created 2 days ago: no reminder.
- Case with `triage_at` set 8 days ago: reminder sent, with the original behavior.

The full suite gives 369 passed and 8 failed. The 8 failures are the same pre-existing ones from before (AI tests needing network, and two database/entity tests). Ruff check and format pass on both changed files.

**Not changed:**
- I didn't fix the reopen handler, which is the real source of NULL `triage_at`. Routing it through the transition dispatcher would stop new cases from getting this, but it's a behavior change in Slack, so I'd like your go-ahead first.
- `case_stable_reminder` has the same `None` problem with `stable_at`, which the logs also show. I left it alone because you asked about the close reminder only.

----- next turn -----

**Recap**

- **Symptom:** Weekly close and stable reminders stopped after the 2025-08-13 deploy. Daily triage reminders kept going because that job has no weekday check.
- **Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `== calendar.MONDAY`. `isoweekday()` is 1-based and `calendar.MONDAY` is 0, so `_is_reminder_day()` was always False. Both weekly jobs gate on it.
- **Deploy:** `main-81d8ae42`, started 2025-08-13 16:40 UTC. `c509d45e` is in that image and not in the previous one, `main-b05613b5`. The first Monday under the new image was 2025-08-18, and its run logged no weekly sends.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`. It fails on the old line and passes on the fix.
- **Nightly TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Cases that reach Triage without `triage_at` fail every evening. The likely source is the Slack reopen button, which sets the status to Triage without running the transition that writes `triage_at`. I haven't confirmed this against production data. The job now counts from `created_at` when `triage_at` is NULL, with tests.
- **Open items:**
  - The reopen button still skips the transition, so new cases can keep getting NULL `triage_at`.
  - `case_stable_reminder` has the same missing-timestamp problem with `stable_at`. I didn't change it.
  - Reminder sends aren't logged, so the 2025-08-18 miss comes from the code path and the absence of send logs rather than a direct record.
  - All fixes are uncommitted in the working tree.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at