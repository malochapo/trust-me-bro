## Recap

**Investigation 1: weekly Monday reminders stopped**
- `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0). The check never passed, so the weekly close reminders for long-running triage and stable cases were never sent. The daily triage reminders don't use that check, which is why they kept arriving.
- Commit `c509d45e` (2025-08-12, "share the weekly reminder check") introduced it. It shipped in image `main-81d8ae42`, which the logs show starting on 2025-08-13 at 16:40Z. The previous image was `main-b05613b5`.
- The last Monday before that deploy was 2025-08-11, so the first Monday that missed its reminders was 2025-08-18.
- The fix compares `date.today().weekday()` with `calendar.MONDAY`. The regression tests are in `tests/case/test_case_scheduled.py`.

**Investigation 2: the evening `TypeError` in the case close reminder**
- `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Triage cases whose `triage_at` is NULL raised a `TypeError` every evening, and they never got their weekly reminder.
- The job now counts from `case.triage_at or case.created_at`, with a test.
- I haven't checked the production data to confirm how those cases ended up without `triage_at`. That part is inferred from the code. `case_stable_reminder` still skips stable cases with no `stable_at`. I left it unchanged.

**Investigation 3: signal deduplication and snoozing**
- Commit `917a0b7b` read the per-filter dedup window as seconds when it is stored and entered in minutes, so a window of 30 became 30 seconds. I fixed it and added a test.
- Commit `086dc910` changed `continue` to `break` on an expired snooze filter. One expired filter then stopped later valid snooze filters from running. I fixed it and added a test.
- Commit `a348bbd2` changed canary handling: canaries are not deduplicated and are ignored when looking for an instance to dedup against.
- Commit `7a9fe810` made the default dedup window for signals without filters configurable. It was 1 hour and the default is now 45 minutes.
- All of this is uncommitted. I only ran the signal and case reminder tests, not the full suite.

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