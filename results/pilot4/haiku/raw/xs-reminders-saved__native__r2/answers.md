**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") broke the Monday check. It replaced the inline `date.today().isoweekday() == 1` with a helper that compares against `calendar.MONDAY`:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday (1–7, Monday first), but `calendar.MONDAY` is 0 (I confirmed both values in the sandbox). So `_is_reminder_day()` is always False, and the weekly branches in `case_close_reminder` (line 49) and `case_stable_reminder` (line 95) never send. The daily triage reminder doesn't call this helper, which is why it still arrives.

**Deploy that shipped it:** `registry.example.com/dispatch:main-81d8ae42`. It started on the scheduler at 2025-08-13 16:40:06 UTC (`scheduler-mhtsgqwwx-q5q2n`) and on the web pod at 16:40:07. `c509d45e` is an ancestor of `81d8ae42`, which is not a commit that changes reminder logic itself. The previous build, `main-b05613b5`, was deployed 2025-07-30 and still used the inline check.

**Evidence in the logs:**
- Monday 2025-08-04 (old build) sent Case close and stable reminders, and Monday 2025-08-11 (old build) also sent them, as the last successful weekly sends.
- Monday 2025-08-18 (new build) sent no Case close or stable reminders. The only weekly lines are the `case_stable_reminder` timer and an error from `case_close_reminder`, and the daily triage reminder still sends.
- The API log has no reminder send lines, so the scheduler log is the only source for send/skip evidence.

**Separate issues I noticed, not the cause:**
- `case_close_reminder` has no `triage_at is None` guard, so it logs a `TypeError` for each triage case with no `triage_at`, every day. The per-case `try/except` contains the failure. Commit `32fa810f` added the `stable_at` guard to `case_stable_reminder` but not the equivalent guard for `triage_at`.
- The `stable_at` crash in `case_stable_reminder` was visible from 2025-07-28 and was fixed in `32fa810f`. That fix shipped in `81d8ae42` too, so the stable path's error disappears after 08-13.

No code was changed. The fix would be to make `_is_reminder_day()` compare against `1` or use `calendar.MONDAY + 1`, or to restore the original inline check. I'd also add the `triage_at` guard in the same change.

----- next turn -----

I saved the findings to project memory so tomorrow's session can pick them up. No code was changed.

Saved to `/tmp/sobre-bench-work/run-f2ecd43baf4c/home/.claude/projects/-tmp-sobre-bench-work-run-f2ecd43baf4c-repo/memory/`:
- `weekly-reminders-broken-by-c509d45e.md` covers the root cause, the deploy, the log evidence, the two related issues, and the proposed fix.
- `MEMORY.md` has a one-line pointer to that file. It didn't exist before, so there were no duplicates to update.

The memory records this:
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compares `isoweekday()` (Monday = 1) to `calendar.MONDAY` (0), so it's always False. Commit `c509d45e` introduced it.
- **Deploy:** `main-81d8ae42`, started 2025-08-13 16:40 UTC. The last weekly sends were on Monday 2025-08-11.
- **Open work:** change the comparison to 1, or restore the inline check. Also add the missing `triage_at is None` guard in `case_close_reminder`, and add a test for a known Monday.

Tomorrow, the memory says to first confirm the `calendar.MONDAY` comparison is still in the file, since the code may have changed since today.

----- next turn -----

Fixed. The weekly Monday reminders were never sent because `_is_reminder_day()` compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so it was always False. I changed it to `date.today().weekday() == calendar.MONDAY` in `src/dispatch/case/scheduled.py`.

The regression test is `tests/case/test_case_scheduled.py`. It freezes `date` and checks every weekday, and the Monday case fails on the old code. All 23 tests in `tests/case` pass. The full suite has 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail on the untouched code, so they predate this change.

The logs show the regression in `main-81d8ae42`, deployed 2025-08-13. Monday 2025-08-11 at 18:00 sent close and stable reminders on the previous build. Monday 2025-08-18 at 18:00 sent none. The memory note I had from yesterday was accurate, and I updated it.

Choices I made:
- I used `weekday()` rather than the `== 1` option my notes suggested, since it matches `calendar.MONDAY` directly.
- I did not commit. The change and the new test file are uncommitted in the working tree.
- I did not fix the separate `case_close_reminder` crash on cases with no `triage_at`. It is caught per case, so it does not stop other reminders, but those cases still get none. It needs its own guard and is a good follow-up.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18