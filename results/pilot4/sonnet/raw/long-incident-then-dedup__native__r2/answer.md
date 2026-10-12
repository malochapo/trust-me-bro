Here is the recap of both investigations. All fixes are in the working tree and nothing is committed.

## Investigation 1: missing Monday reminders and the evening TypeError

**Missing weekly reminders.**
- **Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1 and `calendar.MONDAY` is 0, so the check was never true on a Monday. The weekly close reminders for long-running triage and stable cases were therefore skipped, while the daily triage reminders kept working.
- **Introduced by:** `c509d45e`.
- **Deploy:** image `main-81d8ae42`, started on 2025-08-13 at about 16:40Z (a Wednesday). The first Monday after that was 2025-08-18, so that is the first Monday whose reminders were not sent.
- **Fix:** the check now uses `weekday()`, where Monday is 0.
- **Tests:** `tests/case/test_case_scheduled.py` checks that both weekly jobs send only on Monday.

**Evening TypeError.**
- **Cause:** `case_close_reminder` computes `utcnow() - case.triage_at`, and `triage_at` is `None` for cases that never went through the triage transition flow. The per-case error handling logged the TypeError each evening and skipped those cases.
- **Fix:** the job now counts from `case.triage_at or case.created_at`.
- **Test:** a triage case with `triage_at=None` and `created_at` 10 days ago still gets its reminder, with no error logged.
- **Open point:** `case_stable_reminder` skips cases with no `stable_at` silently. I left it alone, and it could take the same fallback if you want.

## Investigation 2: signal snooze and deduplication

I listed the commits since 2025-05-22 that changed snooze or deduplication, then fixed two regressions that came from them.

- **`a348bbd2`** (2025-05-29): canary signals are no longer deduplicated, and existing canary instances are ignored as dedup candidates.
- **`7a9fe810`** (2025-06-19): the default dedup window for signals without filters, previously a hard-coded 1 hour, became configurable. It is now 45 minutes by default.
- **`086dc910`** (2025-08-07): snooze regression. An expired snooze filter now did `break` instead of `continue`, so any valid filter after it was never checked. I restored `continue` and added a test.
- **`917a0b7b`** (2025-08-14): dedup window regression. It read `SignalFilter.window` as seconds, but it has always been minutes, which is what the UI says. A window of 30 became 30 seconds. I restored minutes in `src/dispatch/signal/service.py` and added a test. I also corrected the stale model comment.
- **Defaults not changed:** the column default (3600) and the schema default (600) are still in place. Read as minutes, they are long windows (60 hours and 10 hours).
- **Existing tests:** some existing tests append filters with `signal.filters.append(...)`, which left the collection empty in my attempts. They may be passing without the filter applied. I didn't check them.

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