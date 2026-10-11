**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. The change was meant to be a pure refactor.

It replaced the inline `date.today().isoweekday() == 1` in `case_close_reminder` and `case_stable_reminder` with a shared helper in `src/dispatch/case/scheduled.py:31`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. I confirmed this by running it. The helper is therefore never true, because `isoweekday()` never returns 0. Both weekly jobs now skip every case on every day. No error is logged, so it fails silently. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why it kept working.

**The deploy that shipped it:** the production redeploy on 2025-08-13 at about 16:40 UTC. The scheduler and web pods both moved from image `main-b05613b5` to `main-81d8ae42`. `81d8ae42` is dated 08-12 and contains `c509d45e`. The 07-30 17:10 deploy (`b05613b5`) predates it.

**Evidence from the logs:**
- "Case close reminder sent" appears 4 times on 07-28, 6 on 08-04 and 5 on 08-11. All of those were on the old image. There are none on 08-18, the first Monday after the redeploy.
- On 08-18 the close and stable jobs run for about 0.03–0.05 seconds and send nothing. Before the deploy they took 1–2 seconds and sent several reminders.

**Separate, unrelated issue:** the old image logged a `TypeError` for cases with no `stable_at` (`datetime - None`) in `case_stable_reminder`. Commit `32fa810f` fixed that and is included in the new image. `case_close_reminder` still logs the same error for any triage case with a null `triage_at`. That is a smaller bug and does not cause the missing reminders.

**Suggested fix, not applied as you asked:** change the helper to compare against `1`, or use `date.today().weekday() == calendar.MONDAY`. A small test of the helper against a Monday date would catch this. Two Mondays of reminders (08-18, and any since) were missed. Cases that were due may need a manual nudge or a one-off run after the fix.

----- next turn -----

The weekly reminders are fixed, and the new regression test catches the bug.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both use 0 for Monday, so the check is true on Mondays. I added a comment explaining the difference from `isoweekday()`.

**Test:** `tests/case/test_case_scheduled.py` has two parts.
- **Helper test:** it checks `_is_reminder_day()` on a Monday, a Tuesday and a Sunday.
- **Job tests:** they run the real `case-close-reminder` and `case-stable-reminder` jobs against a 10-day-old case. They assert a reminder is sent on Monday 2025-08-18 and not on Tuesday 2025-08-19. This is the check that failed silently in production.

**Results:**
- With the fix, all 7 new tests pass, and so does the rest of `tests/case`: 22 passed.
- With the fix temporarily reverted, 3 of the new tests fail: the Monday helper case and both jobs' Monday cases.
- The fix is in the working tree, not committed.

**Still to do:** the fix has to be deployed before reminders resume. The Mondays since 08-13 were missed, so you may want to trigger a one-off run, as I noted earlier. The separate `case_close_reminder` error for triage cases with a null `triage_at` is still there.

----- next turn -----

The close-reminder job no longer errors on triage cases with no `triage_at`. Those cases now count from when they were created. The fix and a new test are in the working tree, uncommitted. All 25 tests in `tests/case` pass.

**Cause:** `triage_at` is only set by the new → triage transition (`case_triage_status_flow` in `flows.py`). A case created directly in triage never goes through that transition, so `triage_at` stays null. `case_close_reminder` then computes `datetime.utcnow() - None` for that case every evening. The per-case `try/except` catches it and logs the traceback. I traced this through the code and didn't check the production data, so it's possible other paths also leave `triage_at` empty. Before the fix, those cases never got a weekly reminder.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now computes `datetime.utcnow() - (case.triage_at or case.created_at)`. The change also adds a short comment on why `triage_at` can be missing.

**Test:** `test_close_reminder_falls_back_to_created_at` in `tests/case/test_case_scheduled.py` covers three cases:
- No `triage_at` and created 10 days ago: a reminder is sent.
- No `triage_at` and created 3 days ago: no reminder.
- A real `triage_at` of 10 days ago with a recent `created_at`: a reminder is sent, so `triage_at` still takes priority.

Each case also asserts that nothing is logged as an exception. I checked the tests against the unfixed code, but that run also dropped the earlier Monday fix. The new tests failed, but partly because of the Monday bug rather than the null timestamp alone.

I left `case_stable_reminder` alone. Since commit `32fa810f`, it silently skips cases with no `stable_at`, so those cases never get a reminder either. Falling back to `created_at` there is probably wrong. A stable case is likely old enough to trigger a reminder the moment it becomes stable. Say if you want a different rule for it.

----- next turn -----

**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept working.
- **Weekday bug:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added the helper `_is_reminder_day()`, which compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check is never true. Both `case_close_reminder` and `case_stable_reminder` skip every case, and nothing is logged. The daily triage job doesn't use the helper, so it kept working.
- **Deploy:** the production redeploy on 2025-08-13 at about 16:40 UTC moved the scheduler and web pods from `main-b05613b5` to `main-81d8ae42`, which contains that commit.
- **Evidence:** "Case close reminder sent" appears 4 times on 07-28, 6 on 08-04 and 5 on 08-11. It never appears on 08-18. On 08-18 the jobs ran in about 0.03–0.05 s and sent nothing.
- **Fixes, in the working tree and not committed:**
  - `_is_reminder_day()` now uses `weekday()`.
  - `case_close_reminder` now counts from `triage_at`, or from `created_at` when `triage_at` is missing.
  - `tests/case/test_case_scheduled.py` adds regression tests for both. All 25 tests in `tests/case` pass.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is only set by the new → triage transition, so cases created directly in triage have none. That raised the error every evening, and those cases never got reminders.
- **Open items:**
  - The fixes still need deploying.
  - Mondays after 08-13 were missed, so a one-off run may be needed.
  - `case_stable_reminder` silently skips cases with no `stable_at`, since `32fa810f`. I left that alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at