The Monday reminders broke because of a refactor commit, `c509d45e`, which production picked up in the deploy on 2025-08-13 at about 16:40 UTC. I haven't changed any code.

**Root cause**

`c509d45e` is "refactor(case): share the weekly reminder check", by Jordan Lee, committed 2025-08-12 14:05 PDT. It replaced the inline Monday check in `src/dispatch/case/scheduled.py` with a shared helper:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

- The old code compared `date.today().isoweekday() == 1`.
- `calendar.MONDAY` is `0` (I checked it), but `isoweekday()` returns 1 to 7 with Monday as 1.
- The helper is therefore never true on any day. `isoweekday()` can't return 0.
- `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both use it, so both are silently disabled. Nothing is logged.
- `case_triage_reminder` doesn't use the helper, which is why the daily triage reminders still arrive.
- The fix would be to compare against `1` or use `weekday() == calendar.MONDAY`. I haven't made it.

**Log evidence**

- "Case close reminder sent" appears on every Monday before the deploy, 07-28, 08-04 and 08-11 (4, 6 and 5 sends). On 08-18, the first Monday after the deploy, there are zero.
- Daily "Case triage reminder sent" lines continue through 08-20.
- Nothing else changed around the deploy. The reminder jobs run on the same 18:00 schedule before and after.

**The deploy**

- Every API and scheduler pod was replaced on 2025-08-13 at about 16:40 UTC. The old pods are `web-bsnvb5wc2t` and `scheduler-xdp7k6gs2q`, last seen at 16:40:38–52. The new ones are `web-5dkmr9s9s` and `scheduler-mhtsgqwwx`, first seen at 16:40:06–07.
- That is 09:40 PDT on 08-13, and it is the only rollout in the logs after 07-30.
- The deployed code includes the refactor. Tracebacks from the new pods show `case_close_reminder` at line 47 (`span = ...`), where HEAD has it at line 47. The old pods logged line 43.
- The logs carry no commit SHA, so I inferred the contents of the deploy from commit times. The deploy should include everything up to `81d8ae42` (08-12 14:47 PDT). Commit `3d3bf623` (08-13 11:47 PDT) landed after the rollout. Please confirm the exact image tag or SHA against your deploy records.

**Separate bug, not the cause**

- `case.triage_at` and `case.stable_at` are sometimes `None`. That raises `TypeError: unsupported operand ... 'datetime' and 'NoneType'`, which is caught per case. It shows up daily at 18:00 from 07-28, well before the deploy, and Monday reminders still worked then.
- The stable path was guarded in `32fa810f`, which is dated 2025-08-11 14:25 PDT (08-11 21:25 UTC). The 08-11 18:00 UTC run still threw on the stable path, so that guard had not shipped yet. The close-reminder path still has no guard.

The database "connection refused" errors on 08-15 around 14:40 are unrelated. They hit only that one run.

----- next turn -----

The Monday reminders are fixed, and the new regression test would have caught the bug. I ran only the new test file, not the full suite.

**The fix** is in `src/dispatch/case/scheduled.py`. `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both use 0 for Monday, which `isoweekday()` doesn't. I added a short comment explaining why.

**The regression test** is `tests/case/test_case_scheduled.py`:
- One test checks `_is_reminder_day()` for each of the 7 days of a week and expects it to be true only on Monday.
- A second test runs the real `case-close-reminder` and `case-stable-reminder` jobs. It expects `send_case_close_reminder` to be called once on a Monday and never on a Tuesday.
- To reach the jobs I look them up in `scheduler.registered_tasks`, because `scheduler.add` returns `None`, and I unwrap their decorators.

**Test results**
- With the fix, all 11 tests pass.
- With the fix stashed (the broken code), 3 fail: the Monday case of the helper test and the Monday case of each job test.

The separate `TypeError` for cases with a missing `triage_at` is not fixed. `case_close_reminder` still has no `None` guard like the one `case_stable_reminder` got. I can fix that too if you want.

I haven't committed anything. The fix still needs to go through your normal deploy to reach production.

----- next turn -----

The nightly `TypeError` is fixed: the close reminder job now counts from the case's creation time when `triage_at` is missing. The new tests pass (14 in total, with the earlier fix in place). With both source fixes stashed, 5 of them fail. I haven't committed anything.

**Cause.** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. `triage_at` is a nullable column that is only set when a case passes through `case_triage_status_flow`. Some cases are in the `triage` status without ever going through that flow, so `triage_at` stays `None`. The subtraction then raises, and the per-case `try/except` logs it and skips the case. The error shows up in the logs every day at 18:00, and those cases never got a weekly reminder.

I found two code paths that set the status directly, but I haven't linked either to specific cases in the logs:
- **Reopen button:** `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py` sets `case.status = CaseStatus.triage` directly. It never calls `case_status_transition_flow_dispatcher`.
- **Unexpected transitions:** the `(_, CaseStatus.triage)` branch of the dispatcher only logs a warning and never sets `triage_at`.

The `triage_at` column was added in 2022, so older rows can also be `NULL`.

**Fix.** In `src/dispatch/case/scheduled.py` the job now does `datetime.utcnow() - (case.triage_at or case.created_at)`. `created_at` is already loaded by `get_all_by_status`.

**Tests.** They are in `tests/case/test_case_scheduled.py`:
- A case with no `triage_at` that is 14 days old gets exactly one reminder on a Monday and none on a Tuesday, and nothing is logged as an exception.
- A case with no `triage_at` that is only 2 days old gets no reminder.

I didn't change the code paths that leave `triage_at` unset, so new cases can still arrive without it. The job now handles them, but you may want a separate change that sets `triage_at` in those paths.

----- next turn -----

**Recap**

- **Symptom:** from mid-August the weekly Monday reminders for long-running triage and stable cases stopped. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the inline check `date.today().isoweekday() == 1` with a helper, `_is_reminder_day()`. The helper compares `isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check never matched. It affected the `case-close-reminder` and `case-stable-reminder` jobs and logged nothing.
- **Deploy:** all API and scheduler pods were replaced on 2025-08-13 at about 16:40 UTC.
  - The scheduler logs show the container image changing from `main-b05613b5` to `main-81d8ae42`. The API logs show the same change.
  - `81d8ae42` is dated 2025-08-12 14:47 PDT, after `c509d45e` at 14:05, so I take `c509d45e` to be included. I didn't check git ancestry directly.
  - In my first answer I said the logs carried no image tag. That was wrong. The kubelet "Started container" lines do.
- **Impact:** the close reminders were sent on Mondays 07-28, 08-04 and 08-11. On 08-18, the first Monday after the deploy, none were sent.
- **Fixes (uncommitted, not yet deployed):**
  - `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`.
  - `case_close_reminder` now counts from `created_at` when `triage_at` is missing.
  - Regression tests are in `tests/case/test_case_scheduled.py`. All 14 tests pass with the fixes, and 5 fail without them.
- **Evening `TypeError`:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for some triage cases.
  - The reopen button handler in `interactive.py` sets the status to triage directly, without going through the flow that sets `triage_at`.
  - Cases from before the column was added in 2022 can also have it empty. I haven't tied either path to specific cases in the logs.
  - The error appeared daily from 07-28, before the deploy. It caused those cases to miss their reminder, but it isn't what stopped the weekly reminders.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at