I found the root cause and the deploy that shipped it. No code was changed.

**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It replaces the inline check `date.today().isoweekday() == 1` with `date.today().isoweekday() == calendar.MONDAY`. In Python, `calendar.MONDAY` is `0`, but `isoweekday()` returns 1 for Monday, so the check can never be true. Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) gate on it, so neither sends again. The daily `case_triage_reminder` doesn't use it, which is why those still arrive. The commit was labelled a refactor, so it was probably not reviewed as a behaviour change.

**Deploy:** the scheduler and web pods were replaced on 2025-08-13 at about 16:40 UTC. The new image is `registry.example.com/dispatch:main-81d8ae42`, and the previous one was `main-b05613b5`.
- `c509d45e` is an ancestor of `81d8ae42`. It is not in `b05613b5`, so the deploy that carried it was the 2025-08-13 rollout.
- `81d8ae42` is the image tag from the scheduler's startup line; I assumed the tag is the git commit it was built from.
- `git diff c509d45e 81d8ae42 -- src/dispatch/case/scheduled.py` is empty, so nothing after the refactor touched the file.

**Log evidence:**
- "Case close reminder sent" appears on Mondays 07-28, 08-04 and 08-11 (the last from the old pod, which ran until 08-13 16:40).
- There are no sends on Monday 08-18, the first Monday after the deploy.
- The scheduler logged no errors for this change. The check just silently evaluates false, which is why nobody noticed.

**Unrelated:**
- **`triage_at` TypeError:** the 08-11 fix `32fa810f` guarded `stable_at` being None. `case_close_reminder` still logs a `TypeError` each day on a case whose `triage_at` is None, because `datetime.utcnow() - case.triage_at` has no such guard. Since 08-13 this is the only remaining error from that file.
- **DB outage:** the 08-15 ~14:40 "Connection refused" errors are a separate database outage, not related to the missing reminders.

**Fix, when you want it:** compare against `calendar.MONDAY + 1`, or more simply `date.today().weekday() == calendar.MONDAY`. The `triage_at` None guard is a separate fix.

----- next turn -----

I fixed the weekly reminder check and added a regression test. The new tests pass with the fix. With the fix temporarily reverted, the Monday case fails, so the test does catch this bug. I didn't run the rest of the suite.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` numbers Monday as 0, which matches `calendar.MONDAY`. The old `isoweekday()` numbers Monday as 1, so the check never matched.
- **Test:** `tests/case/test_case_scheduled.py` patches `date.today()` and checks `_is_reminder_day()` for Monday 2025-08-18 (true) and for each other day of that week (false).

I haven't committed anything. The fix still has to go through your normal deploy before Monday reminders resume.

The `triage_at` None error in `case_close_reminder` is still there, as I mentioned earlier. I left it alone because it's a separate issue.

----- next turn -----

The daily TypeError is fixed, and cases with no `triage_at` now get their weekly reminder counted from `created_at`. The new tests and the rest of `tests/case` pass (26 tests). Nothing is committed.

**Cause:** `case_close_reminder` computed `utcnow() - case.triage_at` for every case in Triage. `triage_at` is only set in `case_triage_status_flow`, which runs through the status-transition dispatcher. At least one Slack handler (`plugins/dispatch_slack/case/interactive.py:1427`) sets `case.status = CaseStatus.triage` directly, without running that flow. Those cases have no `triage_at`, so the subtraction hit `None` and the exception was logged once per such case. They were also skipped, so they never got a weekly reminder even before the Monday bug. I only checked that one handler and didn't confirm how the specific cases in the logs were created, so there may be other paths that skip the flow.

**Fix:** in `src/dispatch/case/scheduled.py` the job now uses `case.triage_at or case.created_at`.

**Tests:** `tests/case/test_case_scheduled.py` now has parametrized cases for the job. They check that `triage_at` takes precedence when set (10 days old gets a reminder, 2 days old doesn't). They also check that a missing `triage_at` falls back to `created_at` (10 days old gets a reminder, 2 days old doesn't), and that nothing is logged as an exception. With the source fix reverted, the two fallback cases fail, as does the Monday case from the earlier test.

Two things in the tests you might trip over:
- `CaseFactory` declares `status` as a factory parameter, so passing `status=` doesn't reach the model. That means the existing `new_case` fixture doesn't actually set the status. My test sets `case.status` after creation. I didn't touch the factory.
- `@scheduler.add` returns `None`, so the job function isn't importable by name. The test finds it in `scheduler.registered_tasks` and calls it directly.

The stable reminder doesn't need the same change. The earlier fix (`32fa810f`) already skips cases with no `stable_at`, though that means those cases never get a reminder. I left that as is since you only asked about the close reminder.

----- next turn -----

## Recap

**Missing weekly reminders**
- Commit `c509d45e` (2025-08-12, a "refactor") moved the Monday check into `_is_reminder_day()`. It changed `date.today().isoweekday() == 1` to `isoweekday() == calendar.MONDAY`.
- `calendar.MONDAY` is 0 and `isoweekday()` returns 1 on Monday, so the check was never true. `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both use it, so neither sent again. The daily triage reminder doesn't use it, which is why those kept arriving.
- It reached production with the rollout around 2025-08-13 16:40 UTC, which replaced `main-b05613b5` with `main-81d8ae42`. Reminders were sent normally on Monday 2025-08-11 from the old pod. The first Monday after the rollout was 2025-08-18, and the scheduler log has no "Case close reminder sent" lines that day.
- Fix: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`, with a regression test. The fix is not committed or deployed yet.

**Evening TypeError**
- `case_close_reminder` computed `utcnow() - case.triage_at`. Cases moved to Triage without running the transition flow (for example the Slack handler at `plugins/dispatch_slack/case/interactive.py:1427`) never get a `triage_at`, so the subtraction hit `None`. I confirmed that one path in the code, not the individual cases in the logs.
- Fix: the job now counts from `triage_at`, or from `created_at` when `triage_at` is missing, so those cases get their weekly reminder. The fix is covered by a new test and is also uncommitted and undeployed.

**Unrelated:** a database outage on 2025-08-15 around 14:40 UTC ("Connection refused") shows up in the same logs. It had nothing to do with the missing reminders.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at