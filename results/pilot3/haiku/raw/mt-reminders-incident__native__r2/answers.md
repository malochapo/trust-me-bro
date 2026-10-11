**Root cause:** the weekly-reminder check added in `c509d45e` compares the wrong weekday numbering. Nothing in the reminder config changed, and the daily triage reminder never calls this check, which is why it still works.

**The bug:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` is:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's `weekday()` numbering). I confirmed both values in the sandbox. The comparison is therefore always false, so `case_close_reminder` (triage) and `case_stable_reminder` (stable) never send anything. The previous code, `date.today().isoweekday() == 1`, was correct.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42` started on the scheduler and web pods on 2025-08-13 at 16:40 (`scheduler.log:18851`, `api.log:13201`). `c509d45e` is an ancestor of `81d8ae42` (`fix(case): exclude resolved_by in update (#6183)`), so that deploy shipped it.

**What the logs show:**
- The last Monday run that sent long-running reminders was 2025-08-11 at 18:00 (`scheduler.log:16799`–`16808`). Those ran on the pre-refactor code.
- There are no close-reminder sends on Monday 2025-08-18 or after. The 2025-08-18 and 2025-08-20 runs only show the `case_stable_reminder` timer, with no sends.
- The triage reminder ("Case triage reminder sent…") is unaffected, because `case_triage_reminder` doesn't use `_is_reminder_day()`.

**A separate issue that's already fixed:** the scheduler log has many `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors from 07-28 through 08-12, from `case_stable_reminder` running on cases with no `stable_at`. `32fa810f` (08-11, "not all cases have a stable_at date") added the guard, and it went out in the same 08-13 deploy. The errors stop after that. It didn't cause the missing reminders, but it's a reason the stable reminders were noisy before. Note that the 08-11 close-reminder run also logged an error for `case_close_reminder` (`scheduler.log:16781`), which looks like the same missing-`triage_at` problem in the triage path. I didn't dig into that.

**Suggested fix (not applied):** make `_is_reminder_day()` compare against the same numbering it uses: `date.today().weekday() == calendar.MONDAY`, or `date.today().isoweekday() == 1`. A small test that pins a known Monday would catch this. I didn't check whether a test covers `_is_reminder_day`. No code has been changed.

----- next turn -----

The weekly reminders are fixed and a regression test is in place. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday()` instead of `isoweekday()`. `calendar.MONDAY` is 0 and `weekday()` uses the same numbering, so the check now matches Mondays. This restores the Monday runs for both the triage and stable reminders.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `date` in the scheduled module and checks `_is_reminder_day()` for Monday 2025-08-18 (expects True), plus Tuesday through Sunday (expects False). Results:
- With the fix, `python -m pytest tests/case/test_case_scheduled.py` passes all 7 cases.
- With the old `isoweekday()` line put back, the Monday case fails. I restored the fix afterwards.
- `python -m pytest tests/case tests/case_cost` passes (41 tests).

**Not covered:** the test checks the day-of-week helper, not the full reminder send path. I didn't add an end-to-end test that runs `case_stable_reminder` on a Monday and checks that a message is sent.

----- next turn -----

The nightly TypeError is fixed. Cases with no `triage_at` now count their week from `created_at`, and the new tests pass.

**Cause:** `case_close_reminder` subtracts `case.triage_at` from the current time. Some triage cases have `triage_at = NULL`, so every evening the subtraction raises `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try/except` catches it and logs it, so those cases silently never get a reminder. The log has 16 of these errors, one per evening from 07-28 through 08-12. None appear after that.

The likely source of the NULL is the Slack reopen handler, `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`. It sets `case.status = CaseStatus.triage` directly and skips `case_triage_status_flow`, which is the only place `triage_at` gets set. I haven't confirmed this against production data, and I didn't change that handler, since you asked for the fallback.

**The fix** (`src/dispatch/case/scheduled.py`): `triaged_since = case.triage_at or case.created_at`, and the span is measured from `triaged_since`. Cases that have `triage_at` are unchanged.

**The tests** (`tests/case/test_case_scheduled.py`): they run the undecorated `case-close-reminder` job against a Monday with `get_all_by_status` and `send_case_close_reminder` patched:
- no `triage_at`, created 8 days ago: the reminder is sent
- `triage_at` set 8 days ago, created 30 days ago: the reminder is sent (`triage_at` wins)
- no `triage_at`, created 1 day ago: no reminder

With the old line restored, the no-`triage_at` case fails. `python -m pytest tests/case tests/case_cost` passes (44 tests).

**Not changed:** the stable reminder still skips cases with no `stable_at`, so those cases never get a stable reminder. You didn't ask me to change that, so I left it alone. I can apply the same fallback there if you want it.

----- next turn -----

Here is the recap for the incident report. Nothing is committed yet.

**What happened**

- **Weekly reminders stopped after the 2025-08-13 deploy.** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The condition was never true, so neither the triage nor the stable weekly reminder was sent. The bug came in with the refactor `c509d45e` on 2025-08-12. The image `main-81d8ae42` contains that commit and started on the scheduler and web pods on 2025-08-13 at 16:40. The last weekly sends were on Monday 2025-08-11, before the deploy. None were sent on 2025-08-18 or later in the logs. Fixed by using `weekday()`, with a regression test.
- **Evening TypeError (16 nights, 2025-07-28 to 2025-08-12).** `case_close_reminder` subtracted `triage_at` from the current time. Some triage cases had `triage_at` NULL, so the subtraction raised, and the per-case `try/except` logged it and skipped the case. The likely source is `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py`, which sets the triage status without calling the flow that writes `triage_at`. I haven't confirmed this against production data. The job now counts from `created_at` when `triage_at` is missing, with tests.
- **Also fixed by the same deploy:** the stable reminder's `NoneType` errors came from missing `stable_at` values. `32fa810f` added the guard and shipped in `81d8ae42`. The errors stop after 2025-08-12.

**Open items**

- The stable reminder still skips cases with no `stable_at`, so those cases get no stable reminder. I haven't added a fallback there.
- The reopen handler still skips the triage flow. I haven't changed it.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```