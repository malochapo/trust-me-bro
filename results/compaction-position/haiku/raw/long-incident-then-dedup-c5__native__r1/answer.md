## Recap

**Monday reminders (weekly case reminders not sent)**
- The weekday check in `src/dispatch/case/scheduled.py` compared `date.isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It could never be true, so the weekly reminder never fired. It came in with `c509d45e` (2025-08-12) and shipped in `main-81d8ae42`, which started on 2025-08-13 at 16:40 UTC per the logs.
- The fix uses `date.today().weekday()`. A regression test covers each day of the week.
- The August 11 Monday ran before that deploy, so its reminders went out. The first missed Monday is August 18.

**Nightly TypeError (close reminder)**
- The close-reminder job subtracted `case.triage_at` from the current time. Cases that reached triage without a `triage_at` timestamp caused a TypeError, which is what the nightly logs show. The paths that can leave it unset are the dispatcher fallback in `flows.py` and the Slack reopen button. I could not tie the log errors to a specific case because they carry no case IDs.
- The job now counts from `triage_at`, falling back to `created_at`. Three tests cover the fallback, the too-recent case, and the case where `triage_at` takes precedence.

**Deduplication windows**
- `917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds. A window of 30 became 30 seconds, so instances ten minutes apart were never grouped. The fix restores minutes, and the regression test covers window 30 and window 5.
- Filters created in the UI already store minutes, so they work unchanged.

**Snoozing (valid snooze filter ignored)**
- `086dc910` (2025-08-07) changed the expired-filter check in `filter_snooze` to `break`. An expired snooze filter ended the loop, so a valid snooze filter later in the list was never checked. The fix is `continue`, with a regression test that fails on the old code.

**Canary signals**
- `a348bbd2` (2025-05-29, "don't dedup on canary signals") excludes canary instances from deduplication. Its filter test is still in place.

**Defaults**
- Signals without a filter are grouped with a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, introduced in `7a9fe810`.

**Open items**
- Nothing is committed. The working tree holds all the fixes and tests.
- `SignalFilter.window` still has a column default of 3600 and a schema default of 600. Both now read as minutes, which is wrong for new filters that have no window set.
- The `filter_signal` docstring still says the default window is one hour.
- I could not confirm whether `917a0b7b` is in production. The logs end on 2025-08-20, and the dedup fix may not have deployed yet.

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