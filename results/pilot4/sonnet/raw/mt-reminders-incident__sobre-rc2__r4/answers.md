**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

- **The bug:** the old code tested `date.today().isoweekday() == 1`. The new helper `_is_reminder_day()` tests `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check is never true. I confirmed this for Monday 2025-08-18: `isoweekday()` returned 1 and `calendar.MONDAY` is 0.
- **Effect:** both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) call the helper. Neither can send its weekly reminder any more. The daily triage reminder is a separate job and doesn't use the helper, so it is unaffected. The reminder settings never needed to change.

**Log evidence:**
- `Case close reminder sent to …` appears on every Monday before the deploy: 2025-07-28 (4 sends), 2025-08-04 (6) and 2025-08-11 (5).
- There are no sends on Monday 2025-08-18, even though the 18:00 job ran. The only log line from that run is the incident close reminder.

**The deploy:** the image `registry.example.com/dispatch:main-81d8ae42`, rolled out on 2025-08-13 at about 16:40 UTC.
- The scheduler pod changed from `scheduler-xdp7k6gs2q-w6cj7` to `scheduler-mhtsgqwwx-q5q2n`, and the API pod from `web-bsnvb5wc2t-7lt2t` to `web-5dkmr9s9s-xxktx`.
- The previous image, `main-b05613b5` (deployed 2025-07-30), doesn't contain `c509d45e`. `81d8ae42` does, since it is a descendant of it.
- 08-13 is the first deploy after the 08-12 commit. The diff between the two images is large (83 files), but `c509d45e` is the only change to the Monday check.

**Noise, not the cause:**
- Every 18:00 run, before and after the deploy, logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. It comes from the `triage_at` (close reminder) and `stable_at` (stable reminder) subtraction.
- Those errors are caught per case and predate the deploy. They affect only the cases with missing timestamps, so they didn't stop Monday sends on 07-28, 08-04 or 08-11.
- The only change is that the error's line number moved from 51 to 55, from the extra helper lines.

**Fix, when you want it:** change the helper to compare against `isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`. A small test pinning the Monday behavior would stop a repeat. I haven't changed any code.

----- next turn -----

The Monday check is fixed, and a regression test now covers it. The new tests pass with the fix and three of them fail without it. I haven't run the rest of the suite or committed anything.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now returns `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` both number Monday as 0. The old code compared `isoweekday()`, which numbers Monday as 1, against `calendar.MONDAY`, which is 0.
- **Test:** the new file is `tests/case/test_case_scheduled.py`, and it fakes today's date to the real Mondays and non-Mondays of August 2025. It checks `_is_reminder_day()` directly. It also runs `case_close_reminder` and checks that `send_case_close_reminder` is called on Monday 18 August and not on Tuesday 19 August.
- **Not covered:** `case_stable_reminder` has no test of its own, but it uses the same helper, so the helper tests cover its Monday check.

With the fix stashed, the failing tests were the two Monday cases of the helper check and the Monday close-reminder run. That is the failure you'd have seen on 18 August.

The `datetime - None` errors in the logs (cases with no `triage_at` or `stable_at`) are a separate, older issue. I left them alone. They are caught per case, so they don't block reminders for other cases.

----- next turn -----

The close reminder job now counts from `created_at` when `triage_at` is missing, so those cases get their weekly reminder. All 11 tests in `tests/case/test_case_scheduled.py` pass; I haven't run the rest of the suite or committed anything.

**Cause of the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. The `triage_at` column is nullable, and `src/dispatch/case/flows.py:594` only sets it on a transition into triage. A case created directly in triage, or one that predates the column, has `triage_at = None`. The subtraction then raises, and the per-case `try/except` logs it and skips that case. Those cases could never get a reminder, which is why the error appeared every evening.

**Fix:** in `src/dispatch/case/scheduled.py`, the span is now `datetime.utcnow() - (case.triage_at or case.created_at)`, with a short comment explaining why.

**Tests added:**
- A case with `triage_at=None` and a `created_at` 10 days ago gets the reminder on a Monday, gets none on a Tuesday, and logs no exception.
- A 3-day-old case with no `triage_at` gets no reminder.
- A case with a recent `triage_at` and an old `created_at` gets no reminder, so `triage_at` still takes priority when it exists.

With both fixes stashed, 6 tests fail, including the three new `created_at` cases. That run also reverts the earlier Monday fix, so it doesn't isolate this fix alone.

**Stable reminder job:** `case_stable_reminder` handles a missing `stable_at` by skipping the case silently (commit `32fa810f`). Your ask was about the close reminder job, so I left it alone. Stable cases without `stable_at` still never get a reminder. The same fallback could apply there if you want it.

----- next turn -----

## Recap

**Weekly reminders stopped (root cause).** Commit `c509d45e` (2025-08-12) was a refactor that moved the Monday check into a helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py`. The old inline check was `isoweekday() == 1`. The helper compared `isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1 and `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) use the helper, so neither could send its weekly reminder again. The daily triage reminder doesn't use it and kept working. I changed the helper to use `weekday()`, which also numbers Monday as 0.

**Deploy.** Image `registry.example.com/dispatch:main-81d8ae42` rolled out around 2025-08-13 16:40 UTC. The scheduler and API pods were replaced at that point. The previous image, `main-b05613b5` (2025-07-30), did not contain `c509d45e`. Reminders were sent on 07-28, 08-04 and 08-11, and none on 08-18, although the 18:00 job ran that day.

**Evening TypeError (separate, older issue).** `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set when a case transitions into triage, so cases created in triage or predating the column have `None`. The subtraction failed, the per-case `try/except` logged it, and the case was skipped, so those cases never got a reminder. The job now counts from `created_at` when `triage_at` is missing.

**Tests.** `tests/case/test_case_scheduled.py` holds 11 tests that pass with the fixes. They cover the Monday and non-Monday behavior and the `created_at` fallback. I haven't run the rest of the suite or committed anything.

**Open item.** `case_stable_reminder` still silently skips stable cases that have no `stable_at`. I didn't change it because it wasn't in scope.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at