**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday check into `_is_reminder_day()` and compared the wrong weekday numbering.

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

- `isoweekday()` is 1-based: Monday is 1.
- `calendar.MONDAY` is 0 (`calendar` weeks start at Monday = 0). I checked both values in the sandbox.
- So the check is `1 == 0`, which is never true, and the weekly reminders never send.

The old code was `date.today().isoweekday() == 1`, which was correct. The refactor replaced the literal `1` with `calendar.MONDAY`, mixing two conventions.

The helper is used by both `case_close_reminder` (long-running triage) and `case_stable_reminder` (stable cases), which matches the symptom. `case_triage_reminder` (daily) doesn't use the helper, so it still sends.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, which started on the scheduler at **2025-08-13T16:40:06Z** (scheduler pod `scheduler-mhtsgqwwx-q5q2n`; the web pods rolled out at 16:40:07). Commit `81d8ae42` ("fix(case): exclude resolved_by in update", #6183) contains `c509d45e`, which I confirmed with `git merge-base --is-ancestor`. That deploy also carried `32fa810f` (the `stable_at` guard).

**Corroborating evidence:**
- Before the deploy, the scheduler logged a `stable_at` `NoneType` crash in `case_stable_reminder` every day, and that code path ran on the Monday 2025-08-11 and 2025-08-04 runs. After the deploy, that crash stops, because `32fa810f` guards it.
- The first Monday on the new code was 2025-08-18. The stable reminder ran that evening with no error and no reminder send, since the `_is_reminder_day()` check is false.
- The deployed image was built with the broken check, and no config changed, which matches what you saw.

**Fix (not applied):** make the helper match the original semantics, e.g. `return date.today().weekday() == calendar.MONDAY`, or keep `isoweekday() == 1`. Add a test that pins a known Monday.

**Side issue I noticed:** on 2025-08-18 `case_close_reminder` also logs a `NoneType` error at `case/scheduled.py:47` (`datetime.utcnow() - case.triage_at`) for some triage cases. It's caught per case, so it doesn't block the others, but it has the same shape as the `stable_at` bug and is worth a separate guard.

----- next turn -----

The reminder bug is fixed and a regression test covers it. The full suite has 8 failures that also happen without my change, so they're pre-existing and I left them alone.

**The fix**, in `src/dispatch/case/scheduled.py`:

```python
return date.today().weekday() == calendar.MONDAY
```

`weekday()` is 0-based like `calendar.MONDAY`. The original `isoweekday() == 1` was also correct, but I went with `weekday()` so the helper uses one numbering convention throughout.

**The regression test**, in the new file `tests/case/test_case_scheduled.py`: it pins "today" to each day of one week (Monday 2025-08-11 through Sunday 2025-08-17) and checks that `_is_reminder_day()` is true only on Monday. I checked that it catches the bug: with the broken line restored, the Monday case fails, and with the fix all pass.

**Test results:**
- `python -m pytest tests/case` passes: 22 tests.
- `python -m pytest` on the full suite: 366 passed, 4 skipped, 8 failed.
- The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They fail the same way with my change stashed, so they predate this work.

Nothing is committed. The working tree has the one-line change plus the new test file.

Still open from the earlier investigation: `case_close_reminder` logs a `NoneType` error at `case/scheduled.py:47` for cases with no `triage_at`. It's caught per case, so it doesn't block other cases, but it's the same class of bug as the `stable_at` crash. I didn't touch it since you asked only for the reminder fix.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and the test covers that. I couldn't confirm which production cases hit this, so the cause is partly inferred.

**Cause of the TypeError:** `triage_at` is `NULL` on some cases that are in `triage`, and `case_close_reminder` subtracts it from `utcnow()`. The logs don't name the case, so I couldn't tie the nightly errors to specific rows.

- `triage_at` is only set by the triage transition flows (`case_triage_status_flow`).
- The 2022 migration that added the column (`391f7c3e6992`) didn't backfill existing rows. Cases that were already in triage then would keep `NULL`, and nothing would fix that unless they transition again. This is the most likely source.
- A second path also leaves it unset: the Slack "Re-open" button (`interactive.py`, `reopen_button_click`) sets `status = triage` directly and never runs the transition flow. I did not change this, since you asked for the fallback. It's a separate fix if you want it.

**The fix**, in `src/dispatch/case/scheduled.py`:

```python
triage_started = case.triage_at or case.created_at
span = datetime.utcnow() - triage_started
```

The comment's claim about cases predating the column is my inference, not something I checked against production data. Adjust the wording if you want it strictly factual.

**The tests**, in `tests/case/test_case_scheduled.py`. They run the real job against PostgreSQL, using the raw function the scheduler registers:
- Parametrized over `triage_at` missing or set, and creation recent or old: a missing `triage_at` on a case created 14 days ago sends, a recent creation doesn't, and a set `triage_at` behaves as before.
- A Tuesday run sends nothing.

I checked the failing case: with the fallback removed, the test fails with the same `TypeError`. With the fix, all 12 pass.

**Full suite:** 371 passed, 4 skipped, 8 failed. The 8 failures are the same pre-existing ones in the AI, database, and entity tests, which also fail on the untouched tree.

Nothing is committed. The working tree has the two changes in `scheduled.py` (the Monday fix from before plus this fallback) and the new test file.

----- next turn -----

## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. Daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check") moved the Monday test into `_is_reminder_day()` and compared the wrong weekday numbering. The original `date.today().isoweekday() == 1` was correct. The refactor replaced `1` with `calendar.MONDAY`, which is `0` in Python. `isoweekday()` gives Monday as `1`, so the check was never true and the weekly reminders never sent. The helper gates both `case_close_reminder` (triage) and `case_stable_reminder` (stable), which is why both stopped and the daily triage reminder did not.

**Deploy:** `registry.example.com/dispatch:main-81d8ae42` started on the scheduler at 2025-08-13T16:40:06Z. That commit contains `c509d45e`. The first Monday on that image was 2025-08-18. The 2025-08-18 scheduler run logged no weekly reminder sends.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. The regression test in `tests/case/test_case_scheduled.py` pins each day of one week and fails on the old line.

**Second issue, the nightly TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`, and `triage_at` was `NULL` on some triage cases. The likely source is that the 2022 migration that added the column didn't backfill existing rows. The Slack reopen button also moves a case to triage without running the transition flow, which can leave the timestamp unset. The logs don't name the affected cases, so this is inferred, not confirmed against production data. The fix counts from `created_at` when `triage_at` is missing, and the new tests cover that path.

**Verification:** The case suite passes (27 tests). The full suite gives 371 passed, 4 skipped, and 8 failed. The 8 failures are in the AI, database, and entity tests, and they also fail without my changes.

**Not done:** Nothing is committed. The reopen-button path is still unfixed. Cases that already had `NULL` `triage_at` aren't backfilled.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at