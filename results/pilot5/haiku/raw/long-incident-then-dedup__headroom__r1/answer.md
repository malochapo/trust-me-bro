**Weekly reminders (case close and stable)**

Monday reminders stopped after the deploy that shipped on 2025-08-13. `_is_reminder_day()` compared `calendar.MONDAY` (0) against `date.isoweekday()`, which returns 1 for Monday, so the check was never true. `c509d45e` introduced it on 2025-08-12. The fix uses `date.weekday()`, and a regression test covers Monday through Sunday. The stable reminder uses the same function, so it was affected too. The deploy identity comes from the scheduler log's image tag. I found no deploy record in the repo, so treat it as likely rather than confirmed.

**Evening TypeError (case close reminder)**

The job subtracts `case.triage_at` from the current time. Some triaging cases have no `triage_at`, so every run raised a TypeError for those cases. The per-case `try/except` kept the other cases going. Cases with no `triage_at` now count from `created_at`, and three tests cover this. The source of the NULLs is not confirmed. The likely paths are the "Any -> Triage" branch of the status dispatcher and the Slack reopen button, which set triage without calling the flow that records `triage_at`. Production data would be needed to confirm.

**Deduplication window (GuardDuty)**

`917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds. A 30-minute window became 30 seconds, so instances ten minutes apart opened separate cases. The UI labels the field "Window (minutes)", so the code now reads it as minutes again, and existing filters need no edits. A regression test covers this case.

**Snoozing (Okta)**

`086dc910` (2025-08-07) changed the expired-filter branch of `filter_snooze` from `continue` to `break`. An expired snooze listed first stopped the loop, so a valid snooze after it never applied. The branch is back to `continue`, and a regression test covers it.

**Canary signals**

`a348bbd2` (2025-05-29) stopped canary signals from being deduplicated, and from serving as the match for later instances.

**Default window**

Signals with no filter are grouped within 45 minutes. The value comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which was added in `7a9fe810`.

**State of the work:** nothing is committed. The working tree holds the case-reminder fix, the signal window and snooze fixes, and the tests for each. The signal suite passes (34 passed, 1 skipped). In the last full-suite run, 8 tests in `tests/ai`, `tests/database` and `tests/entity` failed, and they fail without my changes too. Open items: the model defaults for `window` (3600 and 600, while the UI offers 5 to 30 minutes) still need a decision. The stable reminder also skips cases with no `stable_at`, and I left that alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES