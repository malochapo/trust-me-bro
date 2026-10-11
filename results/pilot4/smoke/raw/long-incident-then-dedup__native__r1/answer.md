**Monday weekly reminders**

Assignees stopped getting the Monday reminders for long-running triage and stable cases after the scheduler and web pods started on image `main-81d8ae42` on 2025-08-13. Daily reminders kept working. The cause is that `_is_reminder_day()` compared `date.today().isoweekday()`, which is 1-based with Monday as 1, against `calendar.MONDAY`, which is 0. The comparison was never true. Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") introduced it. The fix uses `weekday()`. Two regression tests cover the Monday check. The Monday 2025-08-11 run had already sent reminders, so the first missed Monday was 2025-08-18.

**Evening TypeError in the case close reminder**

`case_close_reminder` ran `datetime.utcnow() - case.triage_at` for every case in Triage. Some cases in Triage have no `triage_at`, because the `(_, CaseStatus.triage)` transition branch in `src/dispatch/case/flows.py` never calls `case_triage_status_flow`, which is what sets it. Each such case raised a TypeError on each nightly run. The job now counts from `created_at` when `triage_at` is missing, and a test covers this. I did not identify which transition left those specific cases without a timestamp, and I did not change the flow branch.

**Signal deduplication and snoozing**

Three commits changed signal behavior in ways you may want to report:

- **Canary signals** (`a348bbd2`, 2025-05-29): canary instances are excluded from deduplication.
- **Default dedup window** (`7a9fe810`, 2025-06-19): the hard-coded one-hour window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45, so the effective window dropped to 45 minutes.
- **Custom dedup window unit** (`917a0b7b`, 2025-08-14): a filter's window, set in minutes in the UI, was read as seconds. A window of 30 covered only 30 seconds, so instances ten minutes apart opened separate cases. The fix reads it as minutes again, and existing filters work unchanged. The column default changed from 3600 to 60 to match the one-hour comment.
- **Snooze after an expired filter** (`086dc910`, 2025-08-07): an expired snooze filter stopped the loop with `break`, so valid filters listed after it were never checked. The fix uses `continue`, which restores the previous behavior.

Each fix has a regression test that fails without it. The signal tests pass. The full suite has 369 passed, 4 skipped, and 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. Those 8 also fail on the untouched baseline and were not investigated.

**Open items**
- The schema default for a new filter's window, 600 in `SignalFilterBase`, is now read as 600 minutes (10 hours). That was also true before the August change. I did not change it.
- Nothing is committed.

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