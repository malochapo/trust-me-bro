## Recap

**Monday reminders (weekly close reminders not sent)**
- The cause is in `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` is 1-based (Monday is 1), but `calendar.MONDAY` is 0, so the check was never true. Commit `c509d45e` introduced it, and it shipped in image `main-81d8ae42`, deployed 2025-08-13.
- The fix uses `weekday()`, and a regression test checks Monday through Sunday.
- The first missed Monday was 2025-08-18.

**Case close reminder TypeError (evening job)**
- `case_close_reminder` subtracted `case.triage_at` from the current time. Some cases reach triage without `triage_at` being stamped. `case_triage_status_flow` only stamps it on New→Triage and Closed→Triage through the dispatcher. The reopen button and the catch-all `(_, triage)` branch skip it.
- The job now counts from `triage_at`, falling back to `created_at`. Three tests cover it.
- Not fixed: the paths that never stamp `triage_at`.

**Deduplication windows (signal "GuardDuty: Unauthorized API call")**
- Commit `917a0b7b` changed the custom window from minutes to seconds, so a UI window of 30 (minutes) became 30 seconds. The UI label has said "Window (minutes)" since 2023.
- The fix reads the window as minutes again, and the model defaults now match. Existing filters need no edits. A regression test covers a 30-minute window.

**Snoozing (signal "Okta: Impossible travel")**
- Commit `086dc910` changed `continue` to `break` for expired snooze filters in `filter_snooze`. An expired snooze ended the loop, so a valid snooze listed after it was never checked.
- The fix restores `continue`. A regression test covers an expired filter followed by a valid one.

**Status**
- Nothing is committed. All changes are in the working tree.
- The full suite has 8 failures that also occur on a clean HEAD, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. I did not investigate them.
- Commit `7a9fe810` also lowered the default dedup window from one hour to 45 minutes. The docs still say one hour. I did not change either.

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