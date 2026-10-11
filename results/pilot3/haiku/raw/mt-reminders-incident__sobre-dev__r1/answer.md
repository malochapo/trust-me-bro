**Recap**

- **Weekly reminders stopped.** The check in `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It was never true, so the weekly close and stable reminders never sent. Commit `c509d45e` introduced the bug in a refactor. Image `main-81d8ae42` shipped it to the scheduler and web pods on 2025-08-13 at 16:40 UTC. The last Monday with sends was 2025-08-11, and the first missed was 2025-08-18.
- **Evening TypeError.** The close-reminder job subtracted `case.triage_at` from the current time. `triage_at` is only set by the triage transition flow, so cases that reached Triage another way (for example, the Slack reopen handler, or a create-in-triage background task that failed) had it empty. The job now counts from `created_at` in that case. The per-case error handling meant other cases still got their reminders.
- **Fix and tests.** The weekday check now uses `date.today().weekday()`. The close job falls back to `created_at`. The new tests in `tests/case/test_case_scheduled.py` fail on the old code and pass on the fix. All 23 tests in `tests/case` pass against the local PostgreSQL.
- **Not yet done.** Both changes are uncommitted and not deployed. The stable reminder still skips cases with no `stable_at`. The logs don't name the affected cases, so I can't confirm which path produced them.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```