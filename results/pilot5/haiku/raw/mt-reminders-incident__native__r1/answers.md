**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) replaced the Monday check with a helper that compares against the wrong constant. The helper is in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (Monday is 0 in `calendar`'s weekday numbering). I checked both values in the sandbox: `calendar.MONDAY = 0`, and Monday 2025-08-18 has `isoweekday() = 1`. So `_is_reminder_day()` is never true, on any day. The original code compared `isoweekday()` to `1`, so the refactor silently changed the behaviour.

Both weekly paths call this helper: `case_close_reminder` (triage cases, line 49) and `case_stable_reminder` (stable cases, line 95). The daily `case_triage_reminder` does not use it, which matches what you're seeing.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out on 2025-08-13 at 16:40 UTC. The scheduler and web containers both started on that image (`scheduler.log:18851`, `api.log:13201`). `c509d45e` is an ancestor of `81d8ae42`. The logs show no other container starts between 07-30 and 08-13, so this is the first deploy that contains the refactor.

**Log evidence:**
- Monday 2025-07-28, 08-04 and 08-11 each logged case close reminders (the old code on image `b05613b5`, deployed 07-30).
- Monday 2025-08-18 logged only incident close reminders, no case close reminders.
- Daily triage reminders continue through 08-20.

**Side note, not the cause:** `case_stable_reminder` logged a `datetime - NoneType` error at `scheduled.py:101` daily from 07-28 to 08-12. That was a real bug (cases without `stable_at`), fixed in `32fa810f` on 08-11. It stopped logging after the 08-13 deploy. It did not stop the Monday reminders, since the error is caught per case.

I haven't changed any code. When you're ready, the fix is to compare against `1` (or use `date.today().weekday() == calendar.MONDAY`, which is the 0-based form). A test that pins the helper to a known Monday would have caught this.

----- next turn -----

The fix and regression test are in place. I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py:31-33`): `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both are 0-based, so they match. The old `isoweekday()` is 1-based, so it never equalled 0 and the Monday reminders were never sent.

**Regression test** (`tests/case/test_case_scheduled.py`, new file): checks `_is_reminder_day()` for each day of the week of 2025-08-18, with `date` patched in the module. It passes on the fix. I reverted the fix temporarily and confirmed that the Monday case fails on the old line.

**Test results:**
- `tests/case/test_case_scheduled.py`: 7 passed.
- Full suite: 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). They also fail with my changes stashed, so they predate this fix and are unrelated to it.

I didn't add an end-to-end test that runs `case_close_reminder` or `case_stable_reminder` through the database. The helper test covers the bug that shipped, and the scheduler wrappers need project context that the existing tests don't set up.

----- next turn -----

The close reminder job now counts from `created_at` when `triage_at` is missing, so those cases get their weekly reminder. I haven't committed anything.

**Cause:** `case_close_reminder` reads `case.triage_at` with no guard. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Some Slack paths set `case.status = CaseStatus.triage` directly and skip the transition flow, so the timestamp stays `NULL`. The subtraction then raises the `TypeError`. The per-case `try` logs it, so the job continues, but those cases never get a reminder. The direct assignments I found are in `reopen_button_click` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) and `handle_case_participant_role_activity` (`:2246`). I didn't check every other path that could reach triage without the flow.

**Fix** (`src/dispatch/case/scheduled.py:47-49`): the span is now `datetime.utcnow() - (case.triage_at or case.created_at)`, with a comment explaining why.

**Test** (`tests/case/test_case_scheduled.py`): calls the real job function on a triage case with no `triage_at`. A case created 8 days ago gets a reminder. A case created 2 days ago does not. The test reaches the original function through the scheduler registry with `inspect.unwrap`, because `scheduler.add` returns `None`. On the old line, the 8-day case fails with the same `TypeError` as the logs; with the fix, all 9 tests in the file pass.

**Full suite:** 368 passed, 4 skipped, 8 failed. The 8 are the same unrelated AI, database filter and entity failures as before, and they also fail without my changes.

I left `case_stable_reminder` alone. It has the same missing-timestamp issue, but it skips those cases with `if case.stable_at:` instead of counting from a fallback. Stable cases that were set without `stable_at` therefore still get no reminder. If you want the same fallback there, that's a small follow-up.

----- next turn -----

## Recap

**Weekly reminders stopped after the 2025-08-13 deploy.** The weekday check in `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. The refactor that introduced this was `c509d45e`. It shipped in `main-81d8ae42`, which started on the scheduler and web containers at 2025-08-13 16:40 UTC. The Monday 2025-08-11 run was still on the earlier image and sent case close reminders. The 2025-08-18 run sent none. The daily triage reminders were not affected.

**Fix:** `_is_reminder_day()` now uses `weekday()`, which matches `calendar.MONDAY`. A new test, `tests/case/test_case_scheduled.py`, pins the helper to each day of one week. It fails on the old comparison.

**Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` without a guard. Some Slack paths set a case to triage directly and skip `case_triage_status_flow`, which is the only place that sets `triage_at`. Those cases raised the error every evening, so they never received a reminder. The job now counts from `created_at` when `triage_at` is empty. A new test covers a case with no `triage_at` created 8 days ago (reminded) and one created 2 days ago (not reminded).

**Test results:** the new tests pass (9 in the file). The full suite has 368 passed, 4 skipped and 8 failed. The 8 failures are in AI service, database filter and entity service tests. They also fail without these changes.

**Open items:**
- `case_stable_reminder` still skips stable cases with no `stable_at` rather than counting from a fallback. Those cases get no reminder. This is a candidate follow-up, not part of this fix.
- The first-missed date is inferred from logs: the 2025-08-18 run logged no case close reminders, while 07-28, 08-04 and 08-11 each did. The log message is the same for triage and stable reminders, so this can't separate the two.
- No commit has been made. The changes are in the working tree.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```