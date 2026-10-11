**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check, so the weekly reminders can never fire.

**The bug**
- The commit replaced the inline check `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py:31-33`.
- The helper compares `isoweekday()` against `calendar.MONDAY`. `isoweekday()` returns 1–7 with Monday as 1, but `calendar.MONDAY` is 0 (I confirmed this by running it). So `1 == 0` is never true.
- `case_close_reminder` (long-running triage cases) and `case_stable_reminder` both gate on `q >= 1 and _is_reminder_day()`. Neither has sent anything since the change.
- The daily triage reminder doesn't use the helper, which is why it kept working. The refactor looks behaviour-preserving, so review missed it.

**Evidence from the logs**
- "Case close reminder sent" appears on Mondays 2025-07-28 (4), 2025-08-04 (6) and 2025-08-11 (5). There are none on 2025-08-18, and none anywhere after the refactor.
- On 2025-08-18 the scheduler ran `case_close_reminder` and `case_stable_reminder` at 18:00 and sent nothing. The triage reminder to l.nguyen did go out that day.
- The `TypeError` for a case with no `triage_at` is logged every day, before and after the change. It was already there, so it is not what stopped the Monday reminders. It also means `case_close_reminder` skips any triage case that has no `triage_at`.

**The deploy that shipped it**
- Image `registry.example.com/dispatch:main-81d8ae42` started on the scheduler (pod `scheduler-mhtsgqwwx-q5q2n`) and the API (pod `web-5dkmr9s9s-xxktx`) at 2025-08-13 16:40 UTC. The tag's commit is 81d8ae42, "fix(case): exclude resolved_by in update (#6183)".
- It replaced `main-b05613b5`, which had been running since 2025-07-30 17:10. `c509d45e` is not in `b05613b5` and is an ancestor of `81d8ae42`, so this is the first deploy that includes it.
- The scheduler's traceback line numbers move at the same point: line 51 on 08-12 and line 55 on 08-13. That matches the 4 lines the refactor added.
- The 08-13 deploy bundled about 20 commits (`b05613b5..81d8ae42`). Only `c509d45e` touches this logic.

**Fix (not applied):** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. A small unit test of `_is_reminder_day()` with a fixed Monday date would also catch this. Separately, `case_close_reminder` should guard against `triage_at` being `None`, as `case_stable_reminder` does with `stable_at`.

I changed no code.

----- next turn -----

I fixed the Monday check and added a regression test. The new test passes with the fix and fails without it. I only ran the new test file, not the full suite.

- **Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. Both sides of the comparison use 0 for Monday.
- **Test:** `tests/case/test_case_scheduled.py` pins today's date to each day of the week from Monday 2025-08-18 to Sunday 2025-08-24. It asserts the helper is true only on Monday. With the buggy code, the Monday case fails and the other six pass.

I did not touch the separate `triage_at is None` error in `case_close_reminder`. I haven't committed anything.

----- next turn -----

I fixed the `TypeError` and added tests. All 11 tests in `tests/case/test_case_scheduled.py` pass. I did not run the rest of the suite.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at` for every triage case, and `triage_at` can be empty. The only code that sets it is `case_triage_status_flow` in `src/dispatch/case/flows.py`, which runs on a transition into triage and only if `triage_at` is unset. A case created directly in triage status, or one that predates the column, never goes through that flow. `Case.triage_at` has no default, and `case/service.py:create` doesn't set it either. I didn't look at the production data, so I'm inferring that those cases are the ones behind the nightly error, from the code path and the logs.

Each failure was caught by the per-case `try/except` and logged, so the job kept running. Every such case was skipped, so its owner never got the weekly reminder, even before the Monday-check bug.

**Fix:** in `src/dispatch/case/scheduled.py` the job now counts from `case.triage_at or case.created_at`, with a comment explaining why.

**Tests:** I added a parametrized `test_case_close_reminder` to the new test file. It runs the real job function with `get_all_by_status`, `send_case_close_reminder` and the Monday check stubbed. It covers four cases:
- Triaging for 10 days sends a reminder.
- A recent `triage_at` with an old `created_at` does not, so `triage_at` still takes priority.
- No `triage_at` and a 10-day-old case sends a reminder.
- No `triage_at` and a 2-day-old case does not.

With the source changes stashed, the missing-`triage_at` case that should send a reminder fails, along with the Monday-check test.

`scheduler.add` returns `None`, so the decorated job name is `None` in the module. The test therefore looks the function up in `scheduler.registered_tasks` by its name, `case-close-reminder`.

I left `case_stable_reminder` as it was. It already skips cases with no `stable_at`, so those get no reminder at all. You only asked about the close job, so I didn't change that. I haven't committed anything.

----- next turn -----

**Recap**

- **Symptom:** Since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminder kept arriving.
- **Weekday bug:** Commit `c509d45e` (2025-08-12) replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so it is never true. `case_close_reminder` and `case_stable_reminder` both depend on it, so neither sent anything after the change. The daily triage reminder doesn't use the helper, so it was unaffected.
- **Deploy:** `registry.example.com/dispatch:main-81d8ae42` started on the scheduler and API at 2025-08-13 16:40 UTC. It replaced `main-b05613b5`, which does not contain `c509d45e`.
- **Impact:** Reminders were sent on Mondays 07-28, 08-04 and 08-11 (before the deploy). 2025-08-18 was the first Monday after the deploy, and the logs show nothing sent for close or stable cases that day.
- **Evening TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. `triage_at` is only set when a case transitions into triage, so cases created directly in triage, or older than the column, have none. Each such case raised an error that was logged and skipped, so its assignee never got a weekly reminder. This was happening before the deploy as well.
- **Fixes, not committed:**
  - `_is_reminder_day()` now uses `weekday()` against `calendar.MONDAY`.
  - `case_close_reminder` now counts from `triage_at or created_at`.
  - New tests in `tests/case/test_case_scheduled.py` cover the Monday check and the fallback. All 11 pass.
- **Not changed:** `case_stable_reminder` still skips cases with no `stable_at`, so those get no reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at