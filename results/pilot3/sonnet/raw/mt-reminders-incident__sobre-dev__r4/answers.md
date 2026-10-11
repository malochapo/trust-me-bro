**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) broke the Monday check. It was shipped by the production deploy of image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13 16:40Z.

**The bug**
- Before the commit, `case_close_reminder` and `case_stable_reminder` in `src/dispatch/case/scheduled.py` checked `date.today().isoweekday() == 1`. In `isoweekday()`, Monday is 1.
- The refactor moved that check into a new helper, `_is_reminder_day()`, and wrote it as `date.today().isoweekday() == calendar.MONDAY`.
- `calendar.MONDAY` is 0 (I confirmed this by running it), and `isoweekday()` never returns 0. The helper therefore always returns `False`, and neither reminder fires on any day.
- The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why those still arrive.
- The fix is to compare against 1, or to use `date.today().weekday() == calendar.MONDAY`. I haven't changed any code.

**Evidence from the logs**

The scheduler's "Case close reminder sent" lines show:

| Monday | Scheduler image | Close reminders sent |
|---|---|---|
| 07-28 | `main-b05613b5`'s predecessor pod (`scheduler-46x2cb2h2`) | 4 |
| 08-04 | `main-b05613b5` (`scheduler-xdp7k6gs2q`) | 6 |
| 08-11 | `main-b05613b5` (`scheduler-xdp7k6gs2q`) | 5 |
| 08-18 | `main-81d8ae42` (`scheduler-mhtsgqwwx`) | 0 |

- **Deploys in the window:** The kubelet "Started container" lines show only two deploys in the window:
  - 2025-07-30 17:10Z: `main-b05613b5`.
  - 2025-08-13 16:40Z: `main-81d8ae42`.
  - The scheduler and web pods were replaced together each time.
- **Which deploy has the commit:** `c509d45e` is not in `b05613b5` (a 2025-07-29 commit) but is an ancestor of `81d8ae42`. The refactor commit predates the deploy by about a day. The deploy also carried 28 other commits.
- **Traceback line numbers:** In the 08-13 to 08-20 scheduler pod's tracebacks, `case_close_reminder` fails at `scheduled.py` line 55 (the `span = ...` line at 47 and the `log.exception` call at 55). The earlier pod's tracebacks show 43 and 51. In the repo, `span = ...` is at line 41 in `c509d45e~1` and 47 in `c509d45e`. The line-47 and line-55 tracebacks therefore match the post-refactor file.
- **Side effect:** The pods in the window had a Monday gap but no other change. The July 28 and August 4 and 11 Mondays still sent reminders, so settings were not involved.

**Unrelated noise, not the cause:** every day at 18:00 the logs show `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` from `case_close_reminder` (a triage case with `triage_at` of `None`) and, until the 08-13 deploy, from `case_stable_reminder` too. `case_close_reminder` still has no `None` guard. Each failure is caught per case by the `try/except`, so it doesn't stop the other cases, and it was already present when the reminders were still being sent. `32fa810f` (2025-08-11) fixed the stable-case variant.

One thing I did not check: whether the production deploy of `main-81d8ae42` was a build of exactly that commit. I'm taking the image tag at face value.

----- next turn -----

Fixed, with a regression test that fails on the old code and passes on the fix. I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. The old code compared `isoweekday()` to `calendar.MONDAY`, and those use different numbering (Monday is 1 in the first and 0 in the second), so it never matched.

**Test** (`tests/case/test_case_scheduled.py`):
- **Helper test:** It checks `_is_reminder_day()` on each day of a Monday-to-Sunday week and expects `True` only on Monday.
- **Task test:** It runs the registered `case-close-reminder` task with a triage case that is 10 days old. It expects `send_case_close_reminder` to be called on a Monday and not on a Tuesday.

With the fix, all 9 tests pass. With the fix reverted, the Monday cases fail (the Monday helper case and the Monday case for the close-reminder task), so the test would have caught the original regression.

I only ran the new test file, not the full suite. The stable-case reminder uses the same helper, so the fix covers it, but I didn't add a separate test for it.

The unrelated daily `NoneType` error from cases with no `triage_at` is still there. I left it alone as you didn't ask for it. Say if you want a guard added.

----- next turn -----

The TypeError is fixed and covered by a test. Nothing is committed. The new test cases fail on the old code and pass now, and `tests/case` passes (28 tests).

**Cause:** `case_close_reminder` runs `datetime.utcnow() - case.triage_at` for every case in triage status, and some of those cases have `triage_at` set to `None`. `triage_at` is only filled in by `case_triage_status_flow`. Other code paths set `case.status = CaseStatus.triage` directly without calling that flow, for example the two Slack handlers in `src/dispatch/plugins/dispatch_slack/case/interactive.py` (around lines 1427 and 2246). Cases that go through those paths stay in triage with a null `triage_at`.

The error was caught per case, so the other cases still got their reminders. The cases with a null `triage_at` were skipped every evening and logged a traceback. They were also never going to get the weekly reminder.

**Fix** (`src/dispatch/case/scheduled.py`): the job now counts from `case.triage_at or case.created_at`. I haven't confirmed that `created_at` is always set. It's the field you named, and `case_triage_reminder` already counts from it.

**Tests** (added to `tests/case/test_case_scheduled.py`): on a Monday, a case with no `triage_at` and a creation date 10 days ago gets the reminder. One created 3 days ago doesn't. A case with a `triage_at` still counts from that date rather than from `created_at`. Each case also asserts that nothing is logged as an exception.

I did not change the Slack handlers that leave `triage_at` null, so new cases will keep arriving without it. Setting it there would fix the data at the source, but it's a wider change. Do you want me to make it?

----- next turn -----

**Recap**

- **Symptom:** Since mid-August, assignees stopped getting the weekly Monday reminders to close long-running triage and stable cases. Daily triage reminders kept working.
- **Root cause:** Commit `c509d45e` (2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both weekly reminders (close and stable) went silent. The daily triage reminder doesn't use the helper, so it was unaffected.
- **Deploy:** The commit reached production in image `registry.example.com/dispatch:main-81d8ae42`, deployed 2025-08-13 16:40Z. The deploy before it (`main-b05613b5`, 2025-07-30) doesn't contain the commit. Reminders were sent on 07-28, 08-04 and 08-11 and not on 08-18.
- **Fix:** The helper now uses `weekday() == calendar.MONDAY`. A regression test covers it, and the test fails on the old code.
- **Separate daily TypeError:** `case_close_reminder` logged an error every evening for triage cases whose `triage_at` was `None`. Only `case_triage_status_flow` sets that field. Some paths, such as the Slack handlers, set the status to triage directly. The job now counts from `triage_at`, or from `created_at` when `triage_at` is missing. A test covers it.
- **Left open:** The Slack handlers still don't set `triage_at`.
- **Not verified:** Whether the production build of `main-81d8ae42` was exactly that commit. I took the image tag at face value.
- **State:** The fixes and tests are in the working tree, uncommitted. I ran only `tests/case`, not the full suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at