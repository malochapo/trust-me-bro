**Root cause:** the weekly Monday gate in the case reminders can never be true any more. Commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the inline check `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, but `isoweekday()` runs from 1 (Monday) to 7 (Sunday). So the comparison is never true, on any day. The commit swapped the literal `1` for a constant from a different weekday numbering. `weekday()` would have matched `calendar.MONDAY`, but `isoweekday()` does not.

`case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both call `_is_reminder_day()` and silently skip every case. The daily triage reminder, `case_triage_reminder`, has no weekday check, which is why it still works.

**Evidence from the logs:**
- "Case close reminder sent" appears on Mondays 07-28 (4), 08-04 (6) and 08-11 (5). Every one of these is from the pre-deploy pods. There are none on Monday 08-18, the first Monday after the deploy.
- On 08-18 at 18:00 the case reminder jobs ran without crashing, apart from the unrelated `triage_at` error noted below, and sent nothing.
- The tracebacks in `case_close_reminder` moved from `scheduled.py` line 43 to line 47 after the deploy. That 4-line shift matches the helper and the `import calendar` added by this commit, so the new code was running.
- I confirmed `calendar.MONDAY == 0` and `date(2025,8,18).isoweekday() == 1` in Python.

**The deploy:**
- The scheduler and API pods were both replaced at about **2025-08-13 16:40Z**, which is 09:40 PT.
  - Scheduler: `scheduler-xdp7k6gs2q-w6cj7` was replaced by `scheduler-mhtsgqwwx-q5q2n`.
  - API: `web-bsnvb5wc2t-7lt2t` was replaced by `web-5dkmr9s9s-xxktx`.
- It is the only deploy in the window that contains `c509d45e`. The previous deploy, on 07-30 at about 17:10Z, predates the commit.
- Commits landing after about 09:40 PT on 08-13 can't be in it. That includes `3d3bf623` (11:47 PT) and everything later.
- The logs don't record a git SHA, so I can't name the exact release. Going by commit timestamps, the deploy was cut from main somewhere between `c509d45e` (08-12 14:05 PT) and `81d8ae42` (08-12 14:47 PT, the last commit before it). Your deploy or release record for 08-13 will confirm the exact SHA.

**A separate, older issue:** `case_close_reminder` still logs `datetime - None` errors on cases whose `triage_at` is null. This predates the deploy and the per-case try/except contains it. `case_stable_reminder` already guards against a null `stable_at` (`32fa810f`).

I haven't changed any code. The fix would be to compare against `1`, or against `calendar.MONDAY` using `date.today().weekday()`. Cases that missed their Monday reminders on 08-18 and after (and 08-25 and later, if it's still deployed) won't get them retroactively.

----- next turn -----

The weekly Monday reminders are fixed, and there's a regression test that fails on the old code. Nothing is committed.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, which is what `calendar.MONDAY` means. The old `isoweekday()` call counts Monday as 1, so the comparison was never true.

**Test:** `tests/case/test_case_scheduled.py` has two checks:
- `_is_reminder_day()` is true only on a Monday, checked for each day of the week of 2025-08-18.
- `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) send a reminder for a 10-day-old case on a Monday and send nothing on a Tuesday.

With the fix, all 11 tests in the new file pass, and the whole `tests/case` directory passes (26 tests). With the fix stashed, 3 of them fail: the Monday case of `_is_reminder_day()`, plus the Monday case for each of the two reminder tasks. The Tuesday cases pass either way, as expected.

To call the task bodies, the test looks them up in `scheduler.registered_tasks` and unwraps them, because the `scheduler.add` decorator returns `None`. It stubs the date, the case query and the send function, so it doesn't touch the database.

Once this is deployed, the next Monday run will send the reminders again. Cases that missed 08-18 and any Mondays after it won't be sent retroactively. Do you want me to commit this, or open a PR?

----- next turn -----

The nightly TypeError is fixed and has a test. The change isn't committed.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`, and `triage_at` is `None` for some triage cases, so the subtraction raises. The job catches the error per case and logs it, so those cases are skipped every night. They would never have received the weekly reminder either, even before the Monday bug.

**Why `triage_at` can be empty:** it is only set by `case_triage_status_flow` in `src/dispatch/case/flows.py`, which runs on certain transitions. I checked the code paths:
- `case/service.py` `create` takes `status=case_in.status`, so a case created directly in triage never goes through that flow.
- In the transition dispatcher, a move into triage from any state other than new or closed only logs "Unexpected previous state", and that branch doesn't call the flow.

I haven't confirmed from the data which of these produced the affected cases in production.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`. Cases with no `triage_at` get their weekly reminder once they are more than a week old.

**Tests:** I added two to `tests/case/test_case_scheduled.py`. One has a triage case with no `triage_at`, created 10 days ago, on a Monday. It must send a reminder and log no exception. The other is the same case created 2 days ago. It must send nothing and log no exception. All of `tests/case` passes (28 tests). With the `src` change stashed, both new tests fail. That stash also removes the earlier Monday fix, so the other reminder tests fail in that run too.

The cause of `triage_at` being missing is still there. If you want it closed at the source, the flows above could set it. I left that alone because you only asked for the fallback.

----- next turn -----

## Recap

**Weekly reminder outage**
- **Symptom:** assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()`, which compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1 and `calendar.MONDAY` is 0, so the check was never true. `case_close_reminder` and `case_stable_reminder` both use it and skipped every case. `case_triage_reminder` has no weekday gate, which is why it still worked.
- **Deploy:** the kubelet "Started container" lines in the logs give the image tag. At about 2025-08-13 16:40Z both the scheduler and the API moved from `main-b05613b5` to `main-81d8ae42`. I confirmed with git that `c509d45e` is in `81d8ae42` and not in `b05613b5`. In my first answer I said the logs recorded no SHA. That was wrong, because I hadn't found those lines.
- **Evidence:** reminders were sent on Mondays 07-28, 08-04 and 08-11, all by the old pods. On 08-18 the jobs ran but sent nothing. Traceback line numbers in `scheduled.py` shifted by 4 after the deploy, matching the new code.
- **Fix:** it uses `weekday()` with `calendar.MONDAY`. The regression tests cover each day of the week and both reminder jobs.

**Evening TypeError**
- **Cause:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for some triage cases. `triage_at` is only set by `case_triage_status_flow`. Cases created directly in triage, or moved into triage from a state other than new or closed, never get it. I haven't confirmed from the data which of these produced the affected cases.
- **Fix:** the job now counts from `triage_at or created_at`. Tests cover a missing `triage_at` on an old case and on a recent one.

Both fixes and `tests/case/test_case_scheduled.py` are in the working tree and not committed. `tests/case` passes (28 tests).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at