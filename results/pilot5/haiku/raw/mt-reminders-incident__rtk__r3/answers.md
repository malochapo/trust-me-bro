The regression comes from commit `c509d45e` (Jordan Lee, 2025-08-12), which shipped to production in the scheduler deploy `main-81d8ae42` on 2025-08-13. I haven't changed any code.

**Root cause**

The commit moved the Monday check into a helper:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The original line was `date.today().isoweekday() == 1`, which was correct. The refactor replaced the literal `1` with `calendar.MONDAY`, but the two use different numbering:

- `isoweekday()` is 1–7 with Monday = 1.
- `calendar.MONDAY` is 0 (Monday is 0 in the `weekday()` convention).

I confirmed this with Python: `calendar.MONDAY == 0`, and Monday 2025-08-18 has `isoweekday() == 1`. So `_is_reminder_day()` is never true, and the `q >= 1 and _is_reminder_day()` gate blocks the close and stable reminders on every day, Monday included. The daily triage reminder (`case_triage_reminder`) has no such gate, which is why it still fires. The helper is used by both `case_close_reminder` and `case_stable_reminder`, which explains why both kinds of reminder stopped.

**Timeline**

- `32fa810f` (2025-08-11): last commit before the regression. The Monday check was still `== 1`, so the 2025-08-11 Monday reminders were correct.
- `c509d45e` (2025-08-12, Jordan Lee): "refactor(case): share the weekly reminder check". Introduces the bug.
- `81d8ae42` (2025-08-12, "fix(case): exclude resolved_by in update (#6183)"): this is the commit the scheduler image is tagged with. `c509d45e` is an ancestor of it, confirmed with `git merge-base`.
- Deploy: `scheduler-mhtsgqwwx-q5q2n` started with `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40Z (the web pod was on the same image).
- First affected Monday: 2025-08-18. The scheduler ran `case_stable_reminder` and `case_close_reminder` at 18:00 UTC, but no reminders went out.

**Unrelated issue in the same logs**

Separately, `case_close_reminder` raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` at line 47 (`datetime.utcnow() - case.triage_at`) for at least one case with no `triage_at`. This happens daily and has been in the logs since 2025-07-28, so it predates the regression. The per-case `try/except` catches it, so it doesn't stop other cases. It does mean cases with a null `triage_at` are skipped, and it's worth a separate fix. It did not cause the Monday outage.

**Suggested fix (not applied)**

Make the helper use the same numbering as its call: `date.today().weekday() == calendar.MONDAY`. Alternatively, restore `isoweekday() == 1`. Either way, a small test that asserts `_is_reminder_day()` returns true on a Monday would have caught this.

----- next turn -----

The weekly close and stable reminders are fixed, and a regression test is in place. The test fails on the broken line and passes on the fix. I have not committed anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides of the comparison now use the 0-based Monday = 0 numbering. The previous `isoweekday()` returned 1 for Monday, so it never matched `calendar.MONDAY` (0).

**The test** (`tests/case/test_case_scheduled.py`): a parametrized test that mocks `date.today()` and checks `_is_reminder_day()` on a Monday (True) and on a Sunday, Tuesday and Saturday (False).
- With the fix: 4 passed.
- With the regressed `isoweekday()` line restored: the Monday case fails, as intended.

**Test runs:** `python -m pytest` on the bare shell resolves to `/usr/bin/python3`, which doesn't have the project dependencies. I used the pre-existing dependency environment under the scratchpad directory, with `PYTHONPATH=src`. I first tried to install the project into a new venv, but pip failed on an SSL certificate error. That attempt left an empty venv, which I deleted.
- `tests/case`: 19 passed.
- Full `tests`: 363 passed, 8 failed, 4 skipped.
- The same suite on unmodified code: 362 passed, 9 failed (the 9th is the new test). The 8 failures are the same ones that already failed before my change: 6 in `tests/ai/test_ai_service.py` (these try to resolve hostnames, so they need network access) and `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`. I did not investigate those two further.

**Not addressed:** the `TypeError` from `case.triage_at` being `None` in `case_close_reminder` is still there. It's caught per case, so it doesn't block the others, and I left it alone because it's a separate fix.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and there's a test for it. I have not changed the code that leaves `triage_at` empty.

**What causes the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. A case in triage with `triage_at = NULL` makes that subtraction fail. The per-case `try/except` catches it and logs it, which is why it repeats every evening. `triage_at` is only set in `case_triage_status_flow`, and some paths into triage never run that flow:
- **Dispatcher catch-all:** `case_status_transition_flow_dispatcher` (`src/dispatch/case/flows.py:766`) has a `(_, triage)` branch that only logs a warning. Any move to triage from a status other than new or closed (for example, stable or escalated) leaves `triage_at` empty.
- **Slack reopen button:** `reopen_button_click` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets `case.status = CaseStatus.triage` directly and never calls the flow.
- **API update:** `case/service.py:380` assigns the status directly. The update flow does run the dispatcher afterwards, so this path is covered only when the previous status is new or closed.

I could not confirm which path produced the production rows. The logs have no case IDs and no "Transitioning Case status" lines, so they can't tie a null to a path.

**The fix** (`src/dispatch/case/scheduled.py:47-49`): `triage_started_at = case.triage_at or case.created_at`, and the span is computed from that. Cases with a timestamp behave as before.

**The tests** (`tests/case/test_case_scheduled.py`): both call the job body through the scheduler registry, with `_is_reminder_day` patched to Monday and `send_case_close_reminder` mocked.
- Triage case, `triage_at` null, created 10 days ago: sends. This failed before the fix with the TypeError and passes now.
- Triage case, `triage_at` null, created 2 days ago: does not send.

`python -m pytest tests/case` (run with the dependency environment first on PATH, `PYTHONPATH=src`): 21 passed.

**Not changed:** the transitions above still leave `triage_at` empty, so the same nulls will keep appearing. Fixing that would mean setting `triage_at` in the catch-all branch and in the two direct-assignment paths. I held off because you asked for the fallback. The stable reminder has its own `if case.stable_at:` guard, so it skips such cases silently rather than erroring.

----- next turn -----

## Recap

**Weekly reminders stopped after a regression.** Since the 2025-08-18 Monday run, assignees have not received the weekly close and stable reminders. The daily triage reminders kept working because they don't use the weekday check.

- **Cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. It compares `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, where Monday is 0. The comparison is never true, so the gate blocks every reminder on every day. The original code compared against `1`, which was correct.
- **Deploy:** the scheduler pod (`scheduler-mhtsgqwwx-q5q2n`) started on image `main-81d8ae42` at 2025-08-13T16:40Z. That commit contains `c509d45e`. Monday 2025-08-11 ran before the deploy and was unaffected.
- **Evidence:** on 2025-08-18, `case_stable_reminder` and `case_close_reminder` both ran at 18:00 UTC and sent nothing.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`, parametrized over Monday, Sunday, Tuesday and Saturday. It fails on the broken line and passes on the fix.

**Evening TypeError: cases in triage with no `triage_at`.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. A triage case with a null `triage_at` raised `TypeError`. The per-case `try/except` caught it, so it was logged every evening and those cases never got a reminder.
- **Why `triage_at` is null:** it is only set in `case_triage_status_flow`. Three paths reach triage without running it: the dispatcher's catch-all `(_, triage)` branch (which only logs a warning), the Slack reopen button (`plugins/dispatch_slack/case/interactive.py:1427`), and the direct status assignment in `case/service.py:380`. I could not confirm which path produced the production rows, because the logs have no case IDs or transition records.
- **Fix:** the job now counts from `case.triage_at or case.created_at`. Tests in the same file cover a null `triage_at` on a case created 10 days ago (sends, previously failed with the TypeError) and on one created 2 days ago (does not send).
- **Not changed:** the transitions that leave `triage_at` empty still exist, so nulls will keep appearing. Fixing them is a separate change.

**Test status:** `tests/case` passes, 21 tests. The full suite has 8 failures that also fail on unmodified code: 6 in `tests/ai/test_ai_service.py`, which need network access, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`.

**Working tree:** `src/dispatch/case/scheduled.py` is modified and `tests/case/test_case_scheduled.py` is new. Nothing is committed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at