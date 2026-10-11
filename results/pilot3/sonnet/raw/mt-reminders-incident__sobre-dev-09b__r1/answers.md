**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check.

- **The change:** it replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` to `calendar.MONDAY` (`src/dispatch/case/scheduled.py`).
- **Why it never fires:** `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. So the check can never be true.
- **Where it applies:** both `case_close_reminder` (triage cases) and `case_stable_reminder` use the helper. That matches your report.
- **Daily triage reminders:** `case_triage_reminder` has no day check, so it was untouched. On 2025-08-18 it still sent a reminder.

**Evidence in the logs:**
- "Case close reminder sent to …" lines appear only on Mondays 07-28 (4), 08-04 (6) and 08-11 (5).
- There are none on Monday 08-18, the first Monday after the deploy.
- The 08-18 18:00 run produced no close-reminder or stable-reminder sends. It logged only the `triage_at` error described below.

**The deploy that shipped it:**
- The scheduler and web pods restarted on 2025-08-13 at about 16:40Z. Both started image `registry.example.com/dispatch:main-81d8ae42`, per the kubelet "Started container" lines in both logs.
- The previous image, running from 2025-07-30, was `main-b05613b5`. That image predates `c509d45e` (the merge-base check confirms this).
- `81d8ae42` contains `c509d45e`. It is the "fix(case): exclude resolved_by in update (#6183)" commit, which was only the head of `main` when the image was built. Its own change is unrelated.
- No other deploy appears in the logs between 07-28 and 08-20.

**Side finding:** this is separate from the Monday regression and was already failing before the deploy.
- From 07-28 to 08-12, `case_stable_reminder` crashed on `stable_at` being `None` ("unsupported operand type(s) for -"). Commit `32fa810f` fixed that in the code, and it shipped in the same 08-13 deploy.
- A similar error persists in `case_close_reminder` on 08-18 and 08-19 (`triage_at` is `None`). It is caught per case by the `try/except` and logged, so it only skips those cases. The same `None` check is still missing there.

I haven't changed any code. The fix would be to compare against `1` (or `calendar.MONDAY + 1`, or use `weekday() == calendar.MONDAY`) in `_is_reminder_day()`. I'd also add a test that mocks the date to a Monday.

----- next turn -----

I fixed the Monday check and added a regression test. Nothing is committed yet. The `tests/case` suite passes (29 tests), and `ruff` isn't installed here, so I haven't run lint or format checks.

**The fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` both number Monday as 0, so they match. Both the triage close reminder and the stable reminder go through that helper.

**The tests** are in `tests/case/test_case_scheduled.py`:
- **Helper test:** it checks each of the seven weekdays and expects true only on Monday.
- **Job tests:** `case-close-reminder` and `case-stable-reminder` run on a Monday, a Tuesday and a Sunday. A case that has been open for 10 days gets a reminder only on the Monday.
- **Recent case:** a case that is only 2 days old gets no reminder, even on a Monday.
- **How they run:** the tests fake the date and call the task bodies directly. The task bodies are looked up in `scheduler.registered_tasks`, because the `scheduler.add` decorator returns `None`. Nothing in them needs the database.

**Check against the old code:** I temporarily reverted the fix. Three tests failed: the helper test for Monday and both job tests for Monday. The "no reminder on other days" cases passed either way, since the old check never fired.

**Not fixed:** `case_close_reminder` still raises an error for triage cases where `triage_at` is `None`. We saw it on 08-18 and 08-19. It is caught per case and logged, so those cases are skipped, but they never get reminders. That is a separate change, mirroring the `stable_at` guard from `32fa810f`. I can add it if you want.

----- next turn -----

I fixed the close reminder so it no longer raises that TypeError. It now counts from the case's creation time when `triage_at` is missing. The `tests/case` suite passes (32 tests). The new tests fail without the fallback.

**Cause:** the job computes `datetime.utcnow() - case.triage_at`, and `triage_at` is `None` for some triage cases. The column is nullable, and `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`) when a case moves through the triage transition. Cases that are in triage without having gone through that flow never get the timestamp. Those cases hit the TypeError every evening, and the per-case `try/except` logs it and skips them. That also means they never got their weekly reminder. I didn't work out how those particular cases ended up without a `triage_at`. I only traced where the field gets set.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now uses `case.triage_at or case.created_at`. Cases with a `triage_at` behave as before. The Monday-only rule is unchanged.

**Tests**, added to `tests/case/test_case_scheduled.py`:
- A triage case with no `triage_at` that was created 10 days ago gets a reminder on Monday and none on Tuesday. The test also checks that no exception is logged.
- A triage case with no `triage_at` that was created 2 days ago gets no reminder on Monday.

**How I checked them:** I reverted the whole file, which also removed the earlier Monday fix. Five tests then failed, including the two new "created 10 days ago" tests. Reverting only the fallback would not have shown that clearly.

**Not changed:** `case_stable_reminder` has the same gap with `stable_at`. It skips cases with no `stable_at` instead of falling back, because `32fa810f` added that guard. If you want stable cases to count from creation too, it's a similar one-line change.

----- next turn -----

## Recap

**Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (2025-08-12), moved the Monday test into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` and `case_stable_reminder` use the helper, so neither could send. `case_triage_reminder` has no day check, which is why the daily reminders were unaffected.

**Deploy:** the scheduler and web pods restarted on 2025-08-13 at about 16:40Z on image `registry.example.com/dispatch:main-81d8ae42`. The previous image, `main-b05613b5`, did not contain the commit. The logs show no other deploy in the 07-28 to 08-20 window.

**Evidence:** "Case close reminder sent" lines appear only on the Mondays 07-28, 08-04 and 08-11. There are none on 08-18, the first Monday after the deploy. I only had logs through 08-20, so I couldn't check later Mondays.

**Fixes (uncommitted in the working tree):**
- `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`.
- The nightly TypeError came from `case_close_reminder` subtracting `case.triage_at`, which is `None` for some triage cases. The job now counts from `case.created_at` when `triage_at` is missing.
- `tests/case/test_case_scheduled.py` covers the weekday and fallback cases. It fails on the old code. The `tests/case` suite passed (32 tests) when I last ran it. I didn't run the full test suite.

**Open items:**
- I haven't found out why those triage cases lack `triage_at`.
- `case_stable_reminder` skips cases with no `stable_at`, so those cases still get no reminder.
- Nothing is committed or deployed yet, so production is still affected until the fix ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at