## Recap

**Weekly reminders (Monday bug).** Weekly close and stable reminders stopped after mid-August, while daily triage reminders kept arriving. `_is_reminder_day` in `src/dispatch/case/scheduled.py` compared `calendar.MONDAY` (0) with `date.isoweekday()` (1 for Monday), so the check was always false. Commit `c509d45e` introduced it. The scheduler restarted on image `main-81d8ae42` on 2025-08-13, and the first Monday with no reminders was 2025-08-18. The fix uses `weekday()`, and a parametrized test covers Monday, Tuesday, and Sunday.

**Evening TypeError.** The case close reminder subtracted `case.triage_at` from the current time. `triage_at` is only set by the triage transition flow, so cases that reached triage another way raised a TypeError. The job now falls back to `created_at`, and three tests cover missing `triage_at`, a recent case without it, and a set `triage_at`. I could not confirm which case is failing, because the logs have no case IDs. The likely path is the Slack reopen button, which bypasses the transition flow. That path is unchanged.

**Signal deduplication and snoozing.** Three commits from the batch broke signal handling, and I fixed each one with a regression test:
- `917a0b7b` treated per-filter deduplication windows as seconds instead of minutes. A window of 30 looked back 30 seconds, so instances ten minutes apart were not grouped. The window is back in minutes, and stored values need no edits.
- `086dc910` changed the snooze loop from `continue` to `break` on an expired snooze, so a valid snooze later in the list was never checked. It is back to `continue`.
- `a348bbd2` is the commit that changed canary deduplication. It stopped canary signals from being deduplicated and excluded them as matches. I didn't change this behavior, and I'm listing it as the CANARY commit because it's the one that changed it.

Full test run: 8 failed, 368 passed, 4 skipped. The 8 failures are pre-existing and unrelated to these changes. Nothing is committed.

**Open items for you:**
- The stored window defaults (`window = 3600` on the model, `window: int = 600` in the API schema) now read as 60 hours and 10 hours. Before `917a0b7b` they meant the same, so this is not a new regression, but the comment said "1 hour." I did not change them.
- The `reopen_button_click` path in Slack still sets the case status directly and bypasses the transition flow.

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