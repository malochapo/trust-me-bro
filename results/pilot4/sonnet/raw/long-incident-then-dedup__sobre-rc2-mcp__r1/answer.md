## Recap

**1. Missing Monday reminders (weekday bug)**
- **Cause:** commit `c509d45e` (2025-08-12, "share the weekly reminder check") pulled the Monday test into a helper, `_is_reminder_day()`. It compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check could never be true and no weekly reminder was sent.
- **Which jobs:** it hit both `case_close_reminder` and `case_stable_reminder`. The daily triage reminders don't use the helper, which is why they kept arriving.
- **Deploy:** it reached production on 2025-08-13, a Wednesday, in the `main-81d8ae42` image. The first Monday afterwards was 2025-08-18.
- **Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`, with a regression test in `tests/case/test_case_scheduled.py`.

**2. Evening TypeError in the case close reminder**
- **Cause:** the job computes `datetime.utcnow() - case.triage_at`, and `triage_at` is null for some triage cases. Only the New/Closed→Triage transition flow sets it, so a case created directly in triage never gets it.
- **Fix:** the job now counts from `triage_at or created_at`, with two tests.
- **Caveat:** I inferred this from the code. I didn't check how many production cases have a null `triage_at`.

**3. Signal snooze and deduplication**
- **Dedup windows:** `917a0b7b` (2025-08-14) treated `SignalFilter.window` as seconds. The UI enters it in minutes, so a window of 30 acted as 30 seconds. It now multiplies by 60, with a regression test.
- **Snooze:** `086dc910` (2025-08-07) turned `continue` into `break` for an expired snooze filter. An expired filter listed first then hid a valid one. The fix restores `continue`, with a regression test.
- **Canary signals:** `a348bbd2` (2025-05-29) made canary instances skip deduplication and excluded canary instances from the dedup queries.
- **Default window:** `7a9fe810` made the window for signals with no filter configurable. It dropped from 60 to 45 minutes, and `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` changes it.

All fixes are in the working tree and none are committed. The relevant tests pass.

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