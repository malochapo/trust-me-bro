**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check.

It replaced `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py:31`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, because the `calendar` module numbers weekdays from Monday = 0. `isoweekday()` returns 1 to 7, with Monday = 1. The comparison is never true, so `_is_reminder_day()` always returns `False`.

Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) gate on that helper, so neither sends anything now. The daily triage reminder, `case_triage_reminder`, doesn't use the helper, so it kept working.

**Deploy that shipped it:** the rollout on 2025-08-13 at about 16:40 UTC. The image changed from `registry.example.com/dispatch:main-b05613b5` to `registry.example.com/dispatch:main-81d8ae42`. The log evidence:
- **Scheduler:** `scheduler-xdp7k6gs2q-w6cj7` was replaced by `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40:06Z.
- **API:** `web-bsnvb5wc2t` was replaced by `web-5dkmr9s9s` at 16:40:07Z.
- **Commit check:** `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", dated 2025-08-12 14:47 -0700. The refactor was committed at 14:05 the same day, and `81d8ae42` includes it. The previous image `b05613b5` (2025-07-29) does not.
- **Before and after:** the logs show close reminders sent on Monday 2025-08-04 (6) and 2025-08-11 (5). On Monday 2025-08-18, after the deploy, there were none (0).

The deployed commit is `81d8ae42`, not the refactor itself. The refactor reached production as part of that image.

**Unrelated noise:** `TypeError: datetime - NoneType` errors appear in these jobs for some cases, both before and after the deploy. That is the known `triage_at`/`stable_at`-is-None problem. It is caught per case and didn't cause this outage.

**Fix, when you want it:** use `isoweekday() == 1`, or compare against `calendar.MONDAY` using `weekday()`. Cases whose weekly reminder was skipped on 2025-08-18 and later Mondays will get one on the next Monday after the fix ships. I haven't changed any code.

----- next turn -----

Fixed, with a regression test. I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py`, `_is_reminder_day`): it now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` both count Monday as 0, whereas the old `isoweekday()` counts it as 1. This restores both weekly reminders, the long-running triage one and the stable one.

**Test** (`tests/case/test_case_scheduled.py`):
- **Helper check:** `_is_reminder_day()` returns true only on a Monday, checked across all 7 days.
- **End-to-end check:** the real `case-close-reminder` and `case-stable-reminder` tasks run against a case that is 14 days old. They must send a reminder on Monday and not on Tuesday or Sunday.
- **Setup note:** `scheduler.add` doesn't return the function it wraps, so the test fetches each task from `scheduler.registered_tasks` and strips its decorators with `inspect.unwrap`.

**Results:** all 13 new tests pass with the fix, and the 28 tests in `tests/case` pass. With the fix stashed, the 3 Monday cases fail (the helper on a Monday, and both tasks on a Monday). The reminders never fire in that state, which matches the incident.

----- next turn -----

The TypeError is fixed and has a regression test. All 30 tests in `tests/case` pass. Nothing is committed.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`, and `triage_at` is NULL for some cases in `triage` status. Each time that happens the subtraction raises, the per-case `except` logs it, and the case is skipped. Because of that skip, these cases never got their weekly reminder, even though they were included in the daily run.

The code sets `triage_at` only in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). A case that reaches `triage` without going through that flow keeps a NULL `triage_at`. I didn't trace which path does this in your data. The logs don't say which cases were affected.

**Fix** (`src/dispatch/case/scheduled.py`): the job now counts from `case.triage_at or case.created_at`. `created_at` is already loaded by `get_all_by_status`.

**Test** (`tests/case/test_case_scheduled.py`):
- A triage case with no `triage_at` that was created 14 days ago gets a reminder on a Monday.
- A triage case created 3 days ago does not.
- No exception is logged in either case.

With the fix stashed, both new cases fail.

**Related gap, left unchanged:** `case_stable_reminder` has the same weakness. Commit `32fa810f` added an `if case.stable_at:` guard, so it no longer errors, but it silently skips any stable case without `stable_at`. Those assignees get no weekly reminder and no log line. You only asked about the close reminder, so I didn't touch it. Applying the same `created_at` fallback there is a one-line change if you want it.

----- next turn -----

**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** commit `c509d45e` (Jordan Lee, 2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compares `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The comparison is never true, so both weekly jobs (`case_close_reminder` and `case_stable_reminder`) silently stopped sending.
- **Deploy:** the rollout on 2025-08-13 at about 16:40 UTC moved scheduler and API from image `main-b05613b5` to `main-81d8ae42`. `81d8ae42` includes the refactor and `b05613b5` does not.
- **Timeline:** close reminders went out on Monday 2025-08-04 (6) and 2025-08-11 (5). On Monday 2025-08-18 none were sent. The 11th was before the deploy, so 2025-08-18 is the first miss.
- **Evening TypeError:** some triage cases have no `triage_at`, because only the triage status flow sets it. `datetime.utcnow() - case.triage_at` then fails and that case is skipped.
- **Fixes (uncommitted):**
  - `_is_reminder_day()` now uses `weekday()`.
  - The close reminder falls back to `created_at` when `triage_at` is missing.
  - Regression tests are in `tests/case/test_case_scheduled.py`, and all 30 tests in `tests/case` pass.
- **Open item:** `case_stable_reminder` still silently skips stable cases without `stable_at`.
- **Catch-up:** reminders missed on 2025-08-18 and later Mondays are not sent retroactively. The next Monday after the fix ships will cover them.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at