Here's the recap for the weekly report. Nothing is committed yet, and the changes are in the working tree.

**1. Weekly reminders never sent (weekday bug)**
- Cause: `_is_reminder_day()` compared `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check never passed. It was introduced when the check was moved into a helper and shipped in the 2025-08-13 deploy. Weekly close reminders for both triage and stable cases stopped from the Monday 2025-08-18 run. Daily triage reminders kept going.
- Fix: `date.today().weekday() == calendar.MONDAY`. Regression tests in `tests/case/test_case_scheduled.py` fail on the old code and pass on the fix.

**2. Nightly TypeError (missing triage timestamp)**
- Cause: `case_close_reminder` subtracted `triage_at` from the current time. `triage_at` is only set by `case_triage_status_flow`, and a transition into Triage that isn't in the status-flow match (`flows.py:766`) never sets it. Those cases hit the TypeError every evening.
- Fix: the job now counts from `triage_at`, falling back to `created_at` when it is missing, so those cases get their weekly reminder. Two tests cover this: an old case gets the reminder, and a recent case does not.
- Open: the logs don't include case IDs, so I couldn't confirm which transition produced the affected cases. `case_stable_reminder` still skips cases with no `stable_at`, which is a related gap I did not change.

**3. Dedup windows grouping too few instances**
- Cause: `917a0b7b` changed the per-filter window from minutes to seconds. The UI labels the field "Window (minutes)", so a 30-minute window became 30 seconds.
- Fix: the window is back in minutes, so existing stored values need no edit. The model's comment and column default were updated to match. A regression test checks a 30-minute window that groups an instance 10 minutes earlier and not one 40 minutes earlier.
- Open: I could not check the production filter values, so the size of the impact is unknown.

**4. Snoozes not applied when an expired filter came first**
- Cause: `086dc910` changed `continue` to `break` for expired snooze filters. Once it reached an expired filter, the loop stopped and never checked the valid one.
- Fix: restored `continue`. The rest of `086dc910`'s cleanup is kept. A regression test with an expired filter first fails with `break` and passes with `continue`.

**Test status:** the signal tests pass (35 passed, 1 skipped). The full suite has the same 8 failures as before, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail without these changes.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```