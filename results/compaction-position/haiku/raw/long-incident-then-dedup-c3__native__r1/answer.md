Here is today's recap. Everything below was checked against the repo and logs, except where I note otherwise.

**Investigation 1: missing Monday reminders**

Weekly case-close and case-stable reminders stopped after mid-August, while daily triage reminders kept arriving. The cause is an off-by-one in the weekday check. `calendar.MONDAY` is 0, but `date.isoweekday()` returns 1 for Monday. The check compared the two, so it was never true. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") introduced it. It shipped in image `main-81d8ae42`, which the `scheduler` container started on 2025-08-13 at 16:40 UTC. The 2025-08-11 Monday ran on the previous image, so the first missed Monday is 2025-08-18. The logs don't record individual reminder sends, so that date comes from the deploy time and the code path rather than from a direct log line. The fix changes the check to `isoweekday() == 1` and adds a regression test that fails on the old code. It is in the working tree, not yet deployed.

**Investigation 2: the case-close TypeError every evening**

The job logged a `TypeError` every evening from 2025-07-28 through 2025-08-20. The cause is cases with no `triage_at`. That column was added in the 2022-08-01 migration with no backfill, so cases that entered triage earlier have `NULL`. The job subtracted it from `utcnow()`. The fix counts from `created_at` when `triage_at` is missing, and a regression test covers it. I could not check the production rows, so this is inferred from the migration and the logs.

**Investigation 3: signal dedup and snooze** (reported in this session, not in the summary above)

- Deduplication windows: `917a0b7b` (2025-08-14) read filter windows as seconds, not minutes, so a 30-minute window became 30 seconds. The fix restores minutes. The regression test is `test_filter_actions_deduplicate_window_is_in_minutes`.
- Snoozes: `086dc910` (2025-08-07) changed the expired-snooze `continue` to `break`, so one expired snooze stopped the check for later valid snoozes. The fix restores `continue`. The regression test is `test_filter_action_snooze_with_expired_filter_first`.
- Canary dedup: `a348bbd2` (2025-05-29, "don't dedup on canary signals") excluded canary signals from deduplication.
- Default window: signals with no filter group over 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Before `7a9fe810` (2025-06-19) it was hard-coded at 60 minutes.

Nothing is committed. The working tree holds all the fixes and tests above. Two open issues: the default filter window (`3600`) and the API default (`600`) are read as minutes but are still large, and filters saved through the API between 2025-08-14 and today may have seconds values that now group 60 times more than intended.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```