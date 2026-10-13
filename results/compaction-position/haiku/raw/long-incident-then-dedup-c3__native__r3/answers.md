**Root cause:** commit `c509d45e` broke the Monday check in `src/dispatch/case/scheduled.py:33`. It replaced `date.today().isoweekday() == 1` with `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (Python counts Monday as 0). The condition is never true, so `_is_reminder_day()` returns False every day. Both the triage-case close reminder (`case_close_reminder`) and the stable-case reminder (`case_stable_reminder`) call it, so both stopped. The daily triage reminder (`case_triage_reminder`) has no weekday check, so it still runs.

I confirmed the value with Python: `calendar.MONDAY` is 0, and 2025-08-11 gives `isoweekday()` 1, so `1 == 0` is False.

**Deploy that shipped it:** `81d8ae42` (`fix(case): exclude resolved_by in update (#6183)`, 2025-08-12 14:47 PDT) is on main after `c509d45e` and contains it. Its image, `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13T16:40:06Z and on the web pod at 16:40:07Z. The scheduler log shows the pod change from `scheduler-xdp7k6gs2q` to `scheduler-mhtsgqwwx` at that time.

**Timeline in the logs:**
- Monday 2025-08-04 and Monday 2025-08-11 both sent case close reminders. Those ran on the previous image, `main-b05613b5`, which has the old `== 1` check.
- Monday 2025-08-18 is the first Monday on the new image. It has no case close reminders, only incident close reminders, which still use their own `isoweekday() == 1` check in `incident/scheduled.py:229`.

**Other findings:**
- `case_stable_reminder` also logged a `TypeError` on `stable_at = None` every day from 2025-07-28 until about 2025-08-12. That was a separate crash, fixed by `32fa810f` (`fix(scheduler): not all cases have a stable_at date`), which is already in the deployed image. It is not the cause of the missed Mondays. I did not pin down the exact deploy that made those errors stop.
- The logs show no close reminders on 2025-08-18 for either case type, so the broken check is the only explanation I found.

No code has been changed. The likely fix is one line: compare against `date.today().weekday() == calendar.MONDAY`, or go back to `isoweekday() == 1`. Tests for the reminder day were not in scope, so I did not check whether any cover this, and I did not run the code.

----- next turn -----

The reminder check is fixed and covered by a regression test. The full suite shows 366 passing and 8 failing, and the same 8 fail on the untouched code, so my change didn't cause them.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides count Monday as 0. Before, it compared `isoweekday()` (Monday = 1) against `calendar.MONDAY` (0), so it was never true. This restores both the case close reminder and the stable-case reminder, since both call it. The incident reminder check in `incident/scheduled.py` was not touched.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches the module's `date` so `date.today()` returns a fixed day, then checks `_is_reminder_day()` for every day of the week. Monday must return True and the other six days False. I ran it both ways:
- Against the old code, the Monday case fails, which is the bug.
- With the fix, all 7 cases pass.

**Full suite:** `python -m pytest` gives 366 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). I stashed my changes and ran those three files on the original tree, and the same 8 fail there. I didn't investigate them.

Nothing is committed. The changes are in the working tree: one edited line in `scheduled.py` and the new test file.

----- next turn -----

The close reminder no longer crashes on cases without `triage_at`. Those cases now count from `created_at`, and they get their weekly reminder. The full suite has 369 passing and the same 8 failures as before, none in the reminder code.

**What causes the TypeError:** `case_close_reminder` subtracts `case.triage_at` from the current time. `triage_at` is only set by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), and only when a case moves into triage through the transition flow. A case that reaches triage some other way has `triage_at = None`, and the subtraction raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`.

The most likely source is `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`. It sets `case.status = CaseStatus.triage` directly without calling the flow. That would leave a case that was never triaged, then reopened, with no `triage_at`. The logs don't include case rows, so I couldn't confirm this against production data. I did not change that handler, since you only asked for the fallback.

**Changes:**
- `src/dispatch/case/scheduled.py`: the close reminder now uses `case.triage_at or case.created_at`. This is the only logic change in the job, and a comment explains the fallback.
- `tests/case/test_case_scheduled.py`: three new tests call the job body with stub cases.
  - A case with `triage_at` 8 days old is reminded.
  - A case with no `triage_at` and `created_at` 8 days old is reminded. This test fails on the old code.
  - A case with no `triage_at` and `created_at` 2 days old is not reminded.

**Not changed:** `case_stable_reminder` has the same pattern with `stable_at`, but it skips those cases rather than falling back. You asked only about the close reminder, so I left it alone. Say if you want the same fallback there, with `created_at` as the base.

Nothing is committed.

----- next turn -----



----- next turn -----

Seven commits since 2025-05-22 touch the snooze or dedup logic in `src/dispatch/signal/service.py`. Two of them changed behavior in ways the commit messages don't mention. I haven't changed any code.

**Current windows, as the code applies them:**
- **Default dedup (signals with no dedup filter):** 45 minutes, read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`) and converted to 2700 seconds at `service.py:805`.
- **Dedup filter window:** `SignalFilter.window` is in **seconds**, applied directly at `service.py:845`. The API schema default is `600` (10 minutes, `models.py:282`). The DB column default is `3600` seconds (1 hour, `models.py:206`).
- **Snooze:** no lookback window. A snooze filter is active until its `expiration` timestamp.

**Commits, oldest first:**

1. **`a348bbd2`** (2025-05-29, Will Sheldon, "fix(signal): don't dedup on canary signals"): canary instances skip dedup entirely (early return in `filter_dedup`) and are excluded from the instances that others are deduplicated against. No window change.

2. **`4474af25`** (2025-06-10, Sam Ortega, "log the outcome of each processed signal instance"): adds log lines for filtered and created instances in `signal/flows.py`. Logging only, no decision change.

3. **`7a9fe810`** (2025-06-19, Jordan Lee, "make the default deduplication window configurable"): the no-filter dedup window was hard-coded at **1 hour** and became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` with a default of **45 minutes**. The commit message doesn't mention that the default changed from 60 to 45 minutes.

4. **`086dc910`** (2025-08-07, Sam Ortega, "simplify snooze filter checks"): the snooze loop in `filter_snooze` changed in two ways. The logging for missing `mode` and `action` was removed, so those filters are now skipped silently. Also, an expired snooze filter now hits `break` instead of `continue`, so **any later snooze filters in the list are no longer checked** for that instance. The commit message doesn't say this was intended, and it looks like a bug.

5. **`917a0b7b`** (2025-08-14, Jordan Lee, "share the lookback window computation"): this is labeled a refactor but changes units. Before, `filter_dedup` computed `timedelta(minutes=f.window)`. Now it computes `_window_start(f.window)`, which treats the value as seconds, matching the model comment. Existing filters with `window=600` changed from **10 hours** to **10 minutes**. I haven't checked stored filter rows, so I can't say how many filters have this value.

6. **`d2675cf4`** (2025-07-03, "mask sensitive raw fields before processing"): touches `signal/flows.py` and adds redaction. It doesn't change snooze or dedup logic.

7. **`5e136d7b`** (2025-07-03, "add entity and trigger views to signal instance page"): adds only a `signals` field and a forward-reference rebuild to `models.py`. No logic change.

Commit `dee1699d` (2025-08-15) also appeared in the search but is about suggestions for Security Events, not dedup or snooze.

Two of these need your decision: the `break` in `086dc910`, and the 10-hour-to-10-minute change in `917a0b7b`. I can write up either as a fix if you want.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the filter window from minutes to seconds. The UI still sets minutes, so a stored 30 now means 30 seconds, and two instances ten minutes apart never group. The other commits don't explain this: `086dc910` changed snooze, and `7a9fe810` only changed the no-filter default window.

**Fix:**
- `src/dispatch/signal/service.py`: the filter window is converted with `_window_start(f.window * 60)`, so existing filters keep their stored values and now mean minutes again.
- `src/dispatch/signal/models.py`: the comment on `SignalFilter.window` now says minutes. The column default is unchanged.

**Test:** `test_filter_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` creates two instances ten minutes apart. A window of 30 must group them, and a window of 5 must not. The 30 case failed on the old code and passes now. The existing dedup tests used window=5 with instances created moments apart, which is why they passed under the seconds reading and missed the regression.

**Test results:** `python -m pytest` gives 371 passed, 4 skipped, and the same 8 failures as before (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`). None of those touch signals.

**Left alone:**
- The schema default of 600 (`SignalFilterBase.window`) and the column default of 3600 now read as 10 hours and 60 hours. Those are the same values the code used before `917a0b7b`, but they are probably not what was intended. Tell me if you want them changed.
- The `break` in `086dc910` still stops checking later snooze filters once one has expired. That is a separate bug, and I didn't change it.

Nothing is committed. The changes from the earlier case-close fix are still uncommitted too.

----- next turn -----

The cause is the `break` in `filter_snooze`, introduced by `086dc910` ("refactor(signal): simplify snooze filter checks", 2025-08-07, Sam Ortega). When an expired snooze filter was reached, the loop stopped there, so later snooze filters were never checked. Your Okta user's expired filter came first, so the valid one was never reached. Before that commit the code used `continue`, which skips the expired filter and moves on.

**Fix:** `src/dispatch/signal/service.py` (`filter_snooze`) changes `break` back to `continue` on the expired-filter check.

**Regression test:** `test_filter_actions_snooze_expired_filter_does_not_stop_later_snooze` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter, then a valid one for the same entity, and expects the instance to be snoozed. It fails with the `break` and passes with `continue`.

**Test results:** `python -m pytest` gives 372 passed, 4 skipped, and the same 8 pre-existing failures as before, none in signal code.

Nothing is committed. Uncommitted changes so far:
- The case-close reminder fallback (turn 3).
- The window-in-minutes fix and its test (previous turn).
- This `break` fix and its test.

----- next turn -----

**Monday case reminders (case close and stable)**

Since mid-August, the weekly reminders about long-running triage and stable cases were never sent. `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so the check could never be true. Commit `c509d45e` (2025-08-12, a refactor) introduced the mismatch. It shipped in image `main-81d8ae42`, which started on 2025-08-13. The first Monday without reminders was 2025-08-18. That date comes from the deploy timing and the logs, not from a sent-message record. The fix uses `date.today().weekday()`, and `tests/case/test_case_scheduled.py` covers each day of the week.

**Evening TypeError in the case close reminder**

`case_close_reminder` subtracted `case.triage_at` from the current time. Cases that never went through the triage transition flow have `triage_at = None`, so the subtraction raised `TypeError` and those cases got no reminder. The job now counts from `created_at` when `triage_at` is missing. Three tests cover it, and one fails on the old code. The likely source is the Slack reopen handler, which sets the status directly and bypasses the transition flow. I haven't confirmed that against production data.

**Signal deduplication and snoozing**

- **Dedup windows:** `917a0b7b` (2025-08-14) changed the dedup filter window from minutes to seconds, while the UI still sets minutes. A window of 30 covered 30 seconds, so instances ten minutes apart did not group. `filter_dedup` now converts minutes to seconds, and the model comment says minutes. A regression test covers a 30-minute window and a 5-minute window.
- **Snoozing:** `086dc910` (2025-08-07) changed `continue` to `break` on an expired snooze filter, so later snooze filters were never checked. The "Okta: Impossible travel" instances were not snoozed because of an expired filter that came first. The code is back to `continue`. A regression test puts an expired filter ahead of a valid one.
- **Canary:** `a348bbd2` (2025-05-29) made canary instances skip dedup and excluded them from matches. I didn't change this.

Full suite: 372 passed, 4 skipped, and 8 failures that were already there before these changes (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`). All of today's changes are uncommitted.

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