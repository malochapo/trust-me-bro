**Root cause:** the Monday check in `src/dispatch/case/scheduled.py` can never be true. Commit `c509d45e` changed it to `_is_reminder_day()`, which compares `date.today().isoweekday()` against `calendar.MONDAY`. The two use different numbering:

- `calendar.MONDAY` is `0` (Python's `weekday()` scheme, Monday = 0).
- `isoweekday()` returns `1` for Monday (ISO scheme, Monday = 1).

So `_is_reminder_day()` returns `False` every day. Both weekly paths depend on it: `case_close_reminder` (triage) and `case_stable_reminder` (stable). The daily `case_triage_reminder` doesn't use the helper, so it still runs. That matches your symptoms exactly.

The helper is at lines 31–33 of `scheduled.py`, and both callers are at lines 49 and 95.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which started on the web and scheduler pods on **2025-08-13 at 16:40 UTC**. `81d8ae42` is `fix(case): exclude resolved_by in update (#6183)`, and `c509d45e` is an ancestor of it. `c509d45e` is not in the previous image (`main-b05613b5`), so this is the first release that contained the bug.

**What the logs show:**
- Through the 08-12 scheduler run, `case_stable_reminder` logs an `unsupported operand ... NoneType` error on every daily run. That is the bug fixed in `32fa810f` on 08-11, which shipped in the same 08-13 release.
- From 08-13 onward those errors stop. The reminder runs cleanly on every day, including Monday 2025-08-18 and Monday 2025-08-25, but no reminder is sent and nothing is logged about a send.
- The logs don't show any weekly reminder being sent before the deploy either, but the code path before 08-12 would have run on Mondays 08-04 and 08-11.

**Caveats:**
- The logs don't record sends at all, so "no reminder sent" is inferred from the absence of send or error lines, not from a direct count.
- `tests/` has no test for the scheduled reminders' day check, which is why this got through review.

No code has been changed. When you're ready, the fix is small: make `_is_reminder_day()` use `date.today().weekday() == calendar.MONDAY`, or compare against `calendar.MONDAY + 1` with `isoweekday()`. A test that pins the helper to a known Monday would catch this class of mistake.

----- next turn -----

The weekly reminder check now uses Python's weekday numbering, and there's a regression test for it. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py`, line 33): `_is_reminder_day()` now uses `date.today().weekday()` instead of `isoweekday()`. `calendar.MONDAY` is `0` in Python's numbering, so the two sides of the comparison now match. Both weekly reminders (triage and stable) go through this helper, so both are restored.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it fakes `date.today()` for each day of the week and checks that `_is_reminder_day()` is true only on Monday. I ran it both ways:
- Before the fix: the Monday case fails, which is the bug.
- After the fix: all 7 cases pass.

**Results:** `python -m pytest tests/case` passes (22 tests). I didn't run the whole suite.

**Not covered:** the test checks the helper, not the full scheduled path. Testing `case_stable_reminder` end to end would need the project-context decorator and a database session setup, which I didn't add. The helper is now pinned, so if someone breaks the comparison again, this test will catch it.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and it has regression tests. I haven't committed anything.

**What causes the TypeError:** `case_close_reminder` subtracts `case.triage_at` from `utcnow()`. For some triage cases that column is `NULL`, so the subtraction raises `TypeError`. The error is logged once per case each evening, and the job moves on to the next case. The logs don't say which cases these were.

`triage_at` is set only by `case_triage_status_flow`, which runs when the transition dispatcher sees `(previous, current) == (…, triage)`. Two paths bypass it:
- The Slack triage button and the "triage" button-click handlers (`plugins/dispatch_slack/case/interactive.py`, around lines 1312, 1427, and 2246) assign `case.status = CaseStatus.triage` directly.
- The edit-case submission (`handle_edit_submission_event`, around line 2131) calls the dispatcher before `case_service.update`, so it sees the old status and the transition never fires.

I haven't changed those paths. The fallback is the fix you asked for, and it covers every case that already has no `triage_at`. The ordering bug in the edit-case submission should be fixed separately, and I can do that if you want.

**The fix** (`src/dispatch/case/scheduled.py`): `triage_started_at = case.triage_at or case.created_at`, and the span is measured from that value.

**Tests** (`tests/case/test_case_scheduled.py`): three new tests call the real job through the scheduler registration, with a real session and factory cases, and stub only the day check and the send:
- No `triage_at`, created 8 days ago → reminder sent.
- No `triage_at`, created 2 days ago → no reminder.
- `triage_at` set 8 days ago, created 1 day ago → reminder sent, so the existing behavior is unchanged.

On the pre-fix code, the first test fails. On the fixed code, `python -m pytest tests/case` passes (25 tests).

**Not changed:** `case_stable_reminder` still skips stable cases with no `stable_at` entirely. That's the earlier guard from `32fa810f`. It doesn't throw, but those cases get no reminder. You asked for the fallback only on the close reminder, so I left it. Using `created_at` there would be the same change, if you want it.

----- next turn -----

## Recap

**Weekly reminders stopped after the 2025-08-13 deploy.** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. This suppressed both the triage and stable weekly reminders. Daily triage reminders were unaffected because they don't use the helper.

**The fix** (`src/dispatch/case/scheduled.py`): the helper now uses `weekday()`, which matches `calendar.MONDAY`. Separately, `case_close_reminder` now counts from `created_at` when `triage_at` is missing.

**The evening TypeError** comes from subtracting a `NULL` `triage_at` from `utcnow()`. Triage can be entered without setting `triage_at`: the Slack triage and button handlers assign the status directly, and the edit-case submission runs the transition before the update, so the transition never fires. The logs don't identify which cases. The ordering bug is still there; I haven't fixed it.

**Tests** (`tests/case/test_case_scheduled.py`, new): 7 cases for the weekday check, one per day of the week, and 3 for the close reminder fallback. Both bug tests fail on the pre-fix code. `python -m pytest tests/case` passes (25 tests). Nothing is committed.

**Caveats:** the logs don't record reminder sends, so the missed Mondays come from the code and deploy times, not from send logs. `case_stable_reminder` still skips stable cases with no `stable_at`. I left that alone because you asked only for the close reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at