**Weekly close and stable reminders (Monday):** Monday reminders stopped after a deploy. The Monday check in `case/scheduled.py` was changed from `isoweekday() == calendar.MONDAY` to `weekday() == calendar.MONDAY` in commit `c509d45e`. But `calendar.MONDAY` is 0 and `isoweekday()` returns 1 for Monday, so the check never matched. The change shipped in image `main-81d8ae42` on 2025-08-13 at 16:40Z. The Monday 2025-08-11 reminders still went out from the old pods. Monday 2025-08-18 had zero close sends, so it is the first missed Monday. I fixed the check to use `weekday()` and added a test (`tests/case/test_case_scheduled.py`). That test fails on the old expression and passes on the fix.

**Nightly TypeError:** the case close reminder subtracted `case.triage_at` from now, and `triage_at` is null for some cases in Triage. Those cases raised a TypeError every evening, were caught per case, and never got a reminder. The likely sources are the Slack reopen button, which sets the status without running the triage flow, and rows from before the 2022 migration. The logs don't have case IDs, so I haven't confirmed which records are affected. The job now counts from `created_at` when `triage_at` is missing. Two tests cover this, and the first fails without the fallback.

**Dedup window:** commit `917a0b7b` (2025-08-14) changed filter windows from minutes to seconds, so a window of 30 looked back 30 seconds. The UI labels the field in minutes. I restored minutes, so existing filters need no edits. The regression test is `test_filter_deduplicate_window_is_in_minutes`. The model default is now 60 minutes. The API schema default of 600 is still in effect (now 10 hours), and I left it as is.

**Snooze:** commit `086dc910` (2025-08-07) changed the expired-filter branch of `filter_snooze` from `continue` to `break`, so an expired snooze stopped the check of any valid snooze after it. I restored `continue`. The regression test covers both filter orders.

**Canary signals:** commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated and from being used as dedup matches.

**Open items:** the reopen-button bypass of the triage flow is unchanged, and I haven't checked production for null `triage_at` values. Nothing is committed. The changes are in `case/scheduled.py`, `signal/service.py`, `signal/models.py`, and the matching test files. The test runs used the scratchpad dependency environment because the project venv is missing packages and the network is blocked. The suite result was 368 passed, 4 skipped, and 8 failed, with the 8 failures the same ones that also fail on the original code.

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