**Recap**

- **Weekly reminders stopped after Monday 2025-08-11.** Monday 2025-08-18 was the first Monday with no case close or stable reminders sent. Daily triage reminders kept working.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Aug 12) moved the Monday check into `_is_reminder_day()`. It compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check was never true. The previous code compared with `1` and was correct.
- **Deploy:** the scheduler and web pods rolled out to `main-81d8ae42` on 2025-08-13 at 16:40 UTC. That head commit includes `c509d45e`.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `tests/case/test_case_scheduled.py::test_is_reminder_day` covers every day of one week; it fails on the old code and passes on the new.
- **Evening TypeError:** the close reminder subtracted `case.triage_at` from the current time, and `triage_at` was `None` for some triage cases. The job now uses `case.triage_at or case.created_at`. `test_case_close_reminder_without_triage_at_counts_from_created_at` fails without the fix and passes with it.
- **Likely source of the missing `triage_at`:** the Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets the status to triage without running the transition flow that records `triage_at`. I haven't confirmed this against case data, because the logs don't include case IDs. This bypass is still in the code.
- **Not changed:** the stable reminder still silently skips cases with no `stable_at`, and the reopen bypass is unchanged. Nothing is committed.
- **Reminders not resent:** reminders for 2025-08-18 and later Mondays were not sent and won't be sent automatically. Resending them is a separate decision.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```