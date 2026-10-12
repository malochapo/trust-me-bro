**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the Monday check with a helper that compares against the wrong constant:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 in Python (I checked: `calendar.MONDAY` → `0`). So `_is_reminder_day()` is always False, and the gate `q >= 1 and _is_reminder_day()` never sends. The old code was `isoweekday() == 1`, which was correct, so the refactor changed behavior even though it looked like a no-op.

It affects both `case_close_reminder` (triage) and `case_stable_reminder` (stable), which are the two Monday reminders. The daily `case_triage_reminder` doesn't use the weekday gate, which is why those still arrive. HEAD (`51546e13`) still contains the bug.

**Deploy that shipped it:** the 2025-08-13 production rollout. Both pods were replaced at 16:40Z (09:40 PT):
- scheduler `xdp7k6gs2q` → `mhtsgqwwx` at 16:40:06Z
- api `bsnvb5wc2t`/`6nnvdggn9` → `5dkmr9s9s` at 16:40:07Z

`c509d45e` was merged on 08-12, before that rollout, so it was in the deployed build. The 08-11 Monday run used the old pod and old code, and the first affected Monday is 08-18. The logs don't record a commit hash or version, so the attribution to this rollout is inferred from the pod changes and merge dates, not from an explicit deploy record.

**Other things I checked:**
- The recurring `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors are a separate, pre-existing problem. The `case_stable_reminder` one (line 101) was fixed by `32fa810f` on 08-11. The `case_close_reminder` one (`case.triage_at` is `None`, line 47) still logs daily, but it's caught per case, so it only skips those cases and doesn't explain the missing Monday reminders.
- The logs don't record when reminders are actually sent, so I can't confirm the missing sends directly. The conclusion rests on the code plus the timing.

No code was changed. When you want the fix, it's a one-line change back to `isoweekday() == 1` (or `calendar.MONDAY + 1`, or a named constant), plus a test that pins Monday to the correct value.

----- next turn -----

The reminder bug is fixed and there's a regression test for it. The 8 other test failures also happen on the unmodified code, so they predate this change.

**Fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` now compares `isoweekday()` to `1`, which is Monday in that numbering. I removed the `calendar` import, since that was the source of the mismatch. A short comment notes that `calendar.MONDAY` is `0`, so the next person doesn't reintroduce it.

**Regression tests** (`tests/case/test_case_scheduled.py`, new file):
- `test_is_reminder_day` checks all seven weekdays against the expected Monday-only result. The Monday case is the one that fails on the buggy code.
- `test_case_close_reminder_only_sends_on_monday` and `test_case_stable_reminder_only_sends_on_monday` run the real task functions with a fixed date and stubbed case lookups, and check whether a reminder is sent on Monday and on Tuesday. They reach the underlying functions through the scheduler's registered tasks.

I ran the new file before the fix: the three Monday cases failed (`assert False is True`) and the Tuesday cases passed. After the fix, all 11 tests in the file pass.

**Full suite** (`python -m pytest`): 370 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). I stashed only the source fix and reran those files: the same 8 fail on the original code, so they aren't caused by this change. I didn't investigate them further.

**Lint:** `ruff check` passes, and `ruff format --check` passes on both files. The project uses ruff-format per its pre-commit config, not black.

**Environment:** the venv had no dependencies installed. I installed the project with dev extras into `/tmp/sobre-bench-work/run-2f78b488d806/venv`, using the system CA bundle because PyPI's certificate check failed in this sandbox. Running `python` from the shell didn't always pick up that venv, so I ran pytest with the venv's interpreter directly.

Nothing is committed. The changes are the one-line fix, the removed import, and the new test file.

----- next turn -----

The close reminder no longer crashes when `triage_at` is missing. Such cases now count from `created_at`, so they get their weekly reminder.

**Cause:** `triage_at` is only stamped by `case_triage_status_flow`. Some paths put a case into triage without running it, so the timestamp stays `NULL`, and `datetime.utcnow() - None` raises the `TypeError`. The paths I confirmed:
- **Reopen button** (`reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py`) sets `case.status = CaseStatus.triage` directly and never calls the flow.
- **Status dispatcher's catch-all branch** (`case_status_transition_flow_dispatcher` in `src/dispatch/case/flows.py`): transitions like stable → triage match `(_, CaseStatus.triage)`, which only logs a warning and never stamps `triage_at`.
- Cases triaged before the `triage_at` column was added (2022-08-01 migration) would also have `NULL`. I didn't verify that against the data.

I didn't fix those upstream paths. That's a separate change, and it's the one that would stop the `NULL`s from appearing.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the span is now measured from `case.triage_at or case.created_at`, with a comment explaining the fallback.

**Tests** (`tests/case/test_case_scheduled.py`), added to the existing file:
- A case with no `triage_at` created 8 days ago gets a reminder on Monday. This test failed before the fix with the `TypeError` and passes now.
- A case with no `triage_at` created 2 days ago gets no reminder on Monday.

**Results:** the scheduled-reminder file passes (13 tests) and ruff check and format pass on both files. The full suite has the same 8 pre-existing failures in AI, database, and entity tests as before, with 372 passing.

Two things I left alone, which you may want to decide on:
- `case_stable_reminder` has the same `NULL` problem for `stable_at`, but it already skips those cases silently rather than crashing, so stable cases with no `stable_at` never get a reminder. Counting from `created_at` there too would be a one-line change, but I didn't make it because you only asked about the close reminder.
- Nothing is committed.

----- next turn -----

Here's the recap for the incident report.

**Summary**

- **Weekly reminders stopped after the 2025-08-13 production deploy.** The Monday close and stable reminders never sent again. Daily triage reminders kept working because they don't use the weekday gate.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`, which compares `date.today().isoweekday()` against `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was always false. The old inline check compared against `1` and was correct.
- **Deploy:** the rollout at 2025-08-13 16:40Z (09:40 PT) replaced both the scheduler and API pods. Their logs show the image `registry.example.com/dispatch:main-81d8ae42`, and `c509d45e` is an ancestor of `81d8ae42`, so the deployed build contains the bug.
- **Fix:** `_is_reminder_day()` compares against `1` with a comment explaining the numbering, and the unused `calendar` import is removed. A regression test covers all seven weekdays and both reminder jobs end to end.
- **Separate evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from the current time, and `triage_at` is `NULL` for some cases in triage. The reopen button and the status dispatcher's catch-all branch don't stamp it, and cases triaged before the column existed would also be `NULL`. The job now counts from `created_at` when `triage_at` is missing, with tests for both the 8-day and 2-day cases.
- **Test status:** the full suite has 8 failures in AI, database, and entity tests. They also fail on the original code, so they predate this work.

**Caveats for the report**

- The logs don't record when reminders are sent, so `FIRST_MISSED` comes from the code and the deploy timing, not from observed missing sends. The 2025-08-11 Monday ran on the old pod and old code, so it would have sent.
- The `TypeError` also ran through the stable-reminder path until the `stable_at` guard shipped in `32fa810f`, so the stable-reminder errors in the logs stop around the 08-11 fix, not at the 08-13 deploy.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```