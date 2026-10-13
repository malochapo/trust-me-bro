**Root cause:** `_is_reminder_day()` compares the wrong weekday encoding. `date.today().isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's `weekday()` numbering). So `_is_reminder_day()` is always False, and neither the triage nor the stable Monday reminder is ever sent. The daily triage reminder (`case_triage_reminder`) doesn't use this check, which is why it still arrives.

**Deploy that shipped it:** `main-81d8ae42`, started on the scheduler at 2025-08-13 16:40:06 UTC (and on web at 16:40:07). That image contains commit `c509d45e` "refactor(case): share the weekly reminder check" (authored 2025-08-12 14:05 -0700), which replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`. The previous image, `main-b05613b5`, didn't include that commit, which is why the Monday 2025-08-11 run still sent close reminders (15 "Case close reminder" log lines since 2025-07-28, the last on 08-11). There are none on 08-18.

**Evidence:**
- `python3`: `calendar.MONDAY = 0`, `date(2025,8,11).isoweekday() = 1`.
- `git merge-base --is-ancestor c509d45e 81d8ae42` succeeds, and it fails for `b05613b5`.
- `case/scheduled.py` at HEAD (`51546e13`) still has the bug, so it's live on `main` too.

**Related problem, separate from the Monday regression:** from 2025-07-28 the `case_stable_reminder` job logged a `TypeError` on every daily run (`datetime - NoneType` at `case.stable_at`), because some stable cases have no `stable_at`. That was fixed in `32fa810f` (2025-08-11, which adds the `if case.stable_at:` guard). That fix wasn't in production until `81d8ae42` on 08-13, so the errors ran through 08-12. The guard is in HEAD, so it's fixed on `main`; the Monday regression is the only remaining problem.

**Suggested fix (not applied):** `_is_reminder_day()` should compare with 0-based weekday, e.g. `date.today().weekday() == calendar.MONDAY`, or go back to `isoweekday() == 1`. A unit test that pins a known Monday date would have caught this.

**Not checked:** the scheduler logged one ERROR on 2025-08-18 that I didn't look into. It may be unrelated, but I haven't confirmed that.

I made no code changes.

----- next turn -----

The Monday reminder check is fixed and has a regression test. The case tests pass (22/22), and the new test fails on the old code.

**Changes**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches.
- `tests/case/test_case_scheduled.py` (new): parametrized test over Monday through Sunday of 2025-08-11 to 2025-08-17. It patches `date` in the scheduler module, since no date-freezing library is installed. The Monday case fails on the old code (`assert False is True`) and passes with the fix.

**Full suite:** 366 passed, 4 skipped, 8 failed, 1 error. The 8 failures are in `tests/ai`, `tests/database`, `tests/entity` and `tests/workflow`. I stashed my changes and reran those four directories: the same 8 fail on the original code, so they aren't caused by this change. The error is `tests/workflow/test_workflow_service.py::test_delete` (an `sqlalchemy.exc.O…` error). It appeared only in the full run and not in the four-directory rerun, so it may depend on test order. I didn't investigate it further.

**Not done:** I didn't commit or deploy. The fix only reaches production once it's merged and deployed, and the Monday reminders for the cases that were skipped aren't sent retroactively. If you want the backlog sent, that needs a decision from you.

----- next turn -----



----- next turn -----

The nightly `TypeError` comes from `case.triage_at` being NULL on some cases in triage. The job subtracts it from `datetime.utcnow()`, and the per-case `try/except` logs the error and moves on, so those cases never get a reminder. The fix is in and the case tests pass (25/25), with the new test failing when the fix is reverted.

**Cause:** `triage_at` is only written in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`). Some paths put a case into triage without running that flow, so `triage_at` stays NULL. The clearest one is the Slack handler at `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`, which sets `case.status = CaseStatus.triage` directly. The dispatcher's "Any → Triage" branch also skips the flow and only logs a warning. I didn't confirm which of these produced the cases in the logs, since the log lines don't name the case.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the job now counts from `case.triage_at or case.created_at`. Cases that have a `triage_at` behave as before.

**Tests** (`tests/case/test_case_scheduled.py`, three new tests that run the registered job against real case rows):
- `triage_at` is missing and `created_at` is 8 days ago → reminder sent. This is the one that fails without the fix.
- `triage_at` is missing and `created_at` is 3 days ago → no reminder.
- `triage_at` is 3 days ago and `created_at` is 30 days ago → no reminder, so `triage_at` still takes precedence.

**Not changed:** the stable-case job has the same kind of gap. Commit 32fa810f added an `if case.stable_at:` guard, which stops the crash but also means stable cases with no `stable_at` never get a reminder. You only asked about the close reminder, so I left it alone. Say if you want the same fallback there (count from `created_at`).

I haven't committed. Nothing is retroactive: the cases that were skipped in past runs won't get a reminder until the next Monday run after this is deployed.

----- next turn -----

Since 2025-05-22, four commits changed how Dispatch decides snooze or dedup, or the windows they use. Nothing has been changed. Current code is in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`, `_window_start`) and `src/dispatch/config.py`.

**Commits, oldest first**

1. **`a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals (#6026)"**
   - Canary signal instances skip dedup entirely. They are also excluded from the candidate set when other instances are matched.
   - No window change.

2. **`7a9fe810`, 2025-06-19, "feat(signal): make the default deduplication window configurable"**
   - The default window for signals with no dedup filters went from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes** (env-overridable, `config.py:95`).
   - Stale doc: the `filter_signal` docstring still says "1-hour window".

3. **`086dc910`, 2025-08-07, "refactor(signal): simplify snooze filter checks"**
   - Behaviour change, despite the refactor label. An expired snooze filter used to be skipped (`continue`). It now ends the loop (`break`), so any later active snooze filters on the signal are not checked.
   - The mode check was merged into one condition. The warnings for filters with no mode or no action were dropped.

4. **`917a0b7b`, 2025-08-14, "refactor(signal): share the lookback window computation"**
   - Behaviour change to the custom dedup window. Before, `SignalFilter.window` was applied as **minutes** (`timedelta(minutes=f.window)`). It is now applied as **seconds** through the new `_window_start(seconds)` helper.
   - The model has always documented the field as seconds (default 3600, "1 hour"), so this matches the documented unit. Any existing filter with a stored window now looks back 60 times less far. For example, a 600 value was 10 hours and is now 10 minutes.

**Current values and units**

| Setting | Value | Unit |
|---|---|---|
| Default dedup window (no dedup filters) | 45 (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) | minutes, converted to seconds for the query |
| Custom dedup filter window (`SignalFilter.window`) | model default 3600; API schema default 600 | seconds |
| Snooze | no lookback window; `expiration` datetime | — |

Canary instances are excluded from both the default and custom dedup paths.

**Not verified**
- `d2675cf4` (masks raw fields) and `4474af25` (logs outcomes) touch signal processing. I only grepped their diffs for window and snooze terms and found nothing, so I haven't ruled out side effects.
- I didn't check the UI or API for how window values are entered, so I can't say whether existing filters were created in minutes or seconds.

----- next turn -----

The cause was `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the custom dedup lookback from minutes to seconds. The UI sends minutes ("Window (minutes)", options 5–30), so a window of 30 became a 30-second lookback. Your two instances ten minutes apart fell outside it and opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `filter_dedup` now converts the stored window with `_window_start(f.window * 60)`, so the stored value is read as minutes. Existing filters need no edits, since their stored values are already minutes.
- `src/dispatch/signal/models.py`: the column default went from `60 * 60` to `60`, with the comment now saying minutes. The old default would have meant 60 hours under the restored semantics.
- `src/dispatch/signal/service.py`: updated the `filter_signal` docstring, which said the default window was 1 hour; it's 45 minutes unless `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is set.

**Tests** (`tests/signal/test_signal_service.py`)
- `test_filter_actions_deduplicate_window_is_minutes`: window 30, earlier instance 10 minutes old → deduplicated. This fails on the old code.
- `test_filter_actions_deduplicate_window_expired`: window 30, earlier instance 40 minutes old → not deduplicated.

**Results**
- `tests/signal`: 34 passed, 1 skipped.
- Full suite: 371 passed, 4 skipped, 8 failed. The 8 failures are the same ones in `tests/ai`, `tests/database` and `tests/entity` that fail on the original code. The workflow error from the earlier run didn't appear this time.

**Not changed, for you to decide**
- The API schema default for `window` is still 600. Under minutes that is 10 hours. It was already interpreted as minutes before `917a0b7b`, so I left it alone.
- Filters whose stored window is the old model default of 3600 are read as 3600 minutes (60 hours). That's how they were read before `917a0b7b`, but if any were created by the model default during the seconds period, they'll now dedupe over a longer window than intended. A query for `window = 3600` would show how many there are.
- I haven't committed.

----- next turn -----

The cause is `086dc910` ("refactor(signal): simplify snooze filter checks", 2025-08-07). It changed the expired-snooze check in `filter_snooze` from `continue` to `break`. Once one snooze filter on the signal has expired, the loop stops, so any valid snooze filter listed after it is never checked. That's why the new "Okta: Impossible travel" instances weren't snoozed.

**Fix:** `src/dispatch/signal/service.py`, `filter_snooze`: the expired check goes back to `continue`, so the loop moves on to the next filter. The rest of that function is unchanged.

**Regression test:** `test_filter_actions_snooze_expired_then_valid` in `tests/signal/test_signal_service.py`. It lists an expired snooze filter before a valid one for the same entity, then expects the instance to be snoozed. With the `break` restored it fails, and with `continue` it passes.

**Results**
- `tests/signal`: 35 passed, 1 skipped.
- Full suite: 372 passed, 4 skipped, 8 failed. The 8 failures are the same `tests/ai`, `tests/database` and `tests/entity` tests that fail on the original code.

**Note:** the signal service file changed on disk while I was working. I kept its current contents, which include this fix and the earlier window fix. I haven't committed.

----- next turn -----

Recap for the weekly report.

**Investigation 1: missing Monday reminders (long-running triage and stable cases)**

The weekly reminder check in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. Commit `c509d45e` introduced it on 2025-08-12. It shipped in image `dispatch:main-81d8ae42`, started 2025-08-13. The first Monday without reminders was 2025-08-18. The fix switches the check to `date.today().weekday()`, and a regression test covers all seven weekdays. It fails on the old code and passes on the fixed code.

The same job also logged a `TypeError` every evening. Some cases have no `triage_at`, because only one transition path sets it, and the job subtracted it from the current time. Those cases were silently skipped. The job now counts from `created_at` when `triage_at` is missing, with three tests.

**Investigation 2: deduplication and snoozing**

- **Dedup windows:** commit `917a0b7b` (2025-08-14) changed the custom dedup window from minutes to seconds. The UI sets windows in minutes, so a window of 30 became 30 seconds. The fix reads the stored value as minutes again, so existing filters need no edits. Two regression tests cover this, and one fails on the old code.
- **Snoozing:** commit `086dc910` (2025-08-07) changed the expired-snooze check from `continue` to `break`. An expired filter then stopped the loop, so valid snooze filters listed after it never applied. The fix restores `continue`, with a regression test that fails on the old code.
- **Canary signals:** commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated or used as dedup matches. This was a deliberate fix. It is not part of the regression, so I didn't change it.
- **Default grouping:** signals without a filter are grouped over 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`). The `filter_signal` docstring said 1 hour, and I corrected it.

Test status: the full suite has 372 passed, 4 skipped and 8 failed. The 8 failures are in `tests/ai`, `tests/database` and `tests/entity`, and they also fail on the original code. Nothing is committed or deployed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES