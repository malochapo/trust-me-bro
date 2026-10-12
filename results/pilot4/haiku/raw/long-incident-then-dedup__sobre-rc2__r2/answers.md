**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the Monday test with `_is_reminder_day()`, which compares against `calendar.MONDAY`. That constant is 0, since Python's `calendar` numbers Monday as 0. The original code compared `date.today().isoweekday()` to `1`, which is Monday under ISO numbering. `isoweekday()` returns 1 on Mondays, so `1 == calendar.MONDAY` is always False and the weekly gate never opens. I confirmed this with `python3 -I`: `calendar.MONDAY = 0`, `isoweekday()` on 2025-08-18 is 1, and the comparison is False.

The helper in `src/dispatch/case/scheduled.py:31-33` is shared by `case_close_reminder` (triage) and `case_stable_reminder` (stable). That is why both weekly reminders stopped. The daily `case_triage_reminder` does not use the helper, so it still runs, which matches what you're seeing.

**The deploy:** `main-81d8ae42` was rolled out on 2025-08-13 at 16:40 UTC to the `scheduler` and `web` containers (scheduler.log:18851, api.log:13201). `81d8ae42` is on `main` and has `c509d45e` as an ancestor, so the broken helper shipped in that image. The previous image, `main-b05613b5` (07-30), predates the refactor.

**Corroborating logs:**
- Monday 2025-08-18 at 18:00 UTC: `case_close_reminder` ran, but no reminders were sent. The daily triage reminder did send (`Case triage reminder sent to ...`).
- The earlier stable-reminder errors (`datetime - NoneType`, 07-28 through 08-12) stop after the same 08-13 deploy. That's from `32fa810f` (08-11), which added the `if case.stable_at:` guard and shipped alongside the refactor.

**Related issue, not the cause:** `case_close_reminder` still has no guard for `triage_at is None`. Monday 08-18 logged `datetime - NoneType` at `scheduled.py:55` for at least one triage case. The per-case `try/except` contains it, so other cases still get processed, but that case is skipped. This is worth fixing alongside the main bug.

**Likely fix (not applied):** use `date.today().weekday() == calendar.MONDAY`, or go back to `isoweekday() == 1`. Add a guard for `triage_at` like the one for `stable_at`. I'd also add a test that pins the reminder day to a Monday date, since none caught this.

I haven't changed any code.

----- next turn -----

The reminders now fire on Mondays again, and there's a regression test that fails on the old code and passes with the fix.

**Changes**
- `src/dispatch/case/scheduled.py`:
  - `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use 0-based numbering, so the check matches Monday again. The bug came from comparing `isoweekday()` (Monday is 1) to `calendar.MONDAY` (0).
  - `case_close_reminder` now skips cases with no `triage_at`, the same way `case_stable_reminder` already skips cases with no `stable_at`. Previously those cases raised inside the per-case `try` and were logged as errors.
- `tests/case/test_case_scheduled.py` (new, 9 tests):
  - `_is_reminder_day` returns True on a Monday and False on Sunday, Tuesday, and Saturday.
  - Both weekly reminders send on a Monday and do not send on a Tuesday.
  - A triage case with no `triage_at` is skipped without an error.
  - The tests call the registered task functions directly, against real cases in the PostgreSQL test database. Only the clock and `send_case_close_reminder` are patched.

**Verification**
- `python -m pytest tests/case/test_case_scheduled.py`: 9 passed.
- With the source file reverted to HEAD, the three Monday-send tests fail (`assert [] == [<Case #13>]`), so the test catches the regression.
- `python -m pytest tests/case`: 24 passed.
- `ruff check` passes, and `ruff format` is clean on both files.

**Notes**
- I haven't committed anything. The source change is a modification and the test file is untracked.
- The existing `tests/case/test_case_messaging.py` still runs, but it doesn't cover the reminder logic.

----- next turn -----

The close reminder no longer throws. A case with no `triage_at` is now counted from `created_at`, so it gets its weekly reminder once it is over a week old.

**What causes the TypeError**
- `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. When `triage_at` is NULL, Python raises `TypeError`. The per-case `try` logs it, so the job keeps running but skips that case. That's the error you see every evening from 07-28 to 08-20.
- `triage_at` is only set by `case_triage_status_flow`. The transition flow runs for the web update path and the main Slack triage paths.
- The gap is the Slack **Re-open** button (`reopen_button_click`, `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`). It sets `case.status = CaseStatus.triage` directly and never runs the flow. A case closed straight from New and then reopened therefore ends up in triage with no `triage_at`.
- The logs don't include case IDs, so I can't confirm from the logs which cases are affected. The mechanism comes from the code.

**Changes**
- `src/dispatch/case/scheduled.py`: `case_close_reminder` now uses `triaged_at = case.triage_at or case.created_at`, so a missing triage time falls back to when the case was created. This replaces the skip guard I added last turn.
- `tests/case/test_case_scheduled.py`: the old "skips cases without triage_at" test is replaced by two tests. A triage-less case created 8 days ago gets a reminder on Monday. A triage-less case created 3 days ago doesn't.

**Verification**
- `python -m pytest tests/case`: 25 passed.
- `ruff format` and `ruff check` are clean on both files.
- I didn't re-run the new test against the previous code. Under the old skip guard it would fail, since that code sent nothing for a case with no `triage_at`.

**Not changed**
- The Re-open button still bypasses the transition flow. Fixing it would mean `triage_at` gets set on reopen, which changes behavior for those cases, so I left it for you to decide.
- `case_stable_reminder` still skips cases with no `stable_at`. You asked about the close reminder only.
- Nothing is committed.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 touch the snooze or dedup logic. Two of them change the time windows, and one of those changes what the stored value means.

**Commits**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. Canary instances are skipped as the incoming signal, and excluded from the candidate matches on both the default and filtered paths. No window changed.
2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The default window for signals with no dedup filter was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), default **45 minutes**.
3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. The "missing mode" and "missing action" warnings are gone. The one behavioral change: an expired snooze filter now hits `break` instead of `continue`, so the loop stops there and later snooze filters on the same signal are never checked. No window changed.
4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. Adds `_window_start(seconds)` (`src/dispatch/signal/service.py:784`). This is the commit that changed the units:
   - Default dedup: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, so still 45 minutes.
   - Filter dedup: `f.window` is now passed directly as **seconds**. Before, it was `timedelta(minutes=f.window)`, so the value meant minutes.

**Current windows, as the code applies them**

- **Default dedup** (no dedup filter on the signal): 45 minutes, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **Filtered dedup** (`f.window`): the value is read as seconds. The model column defaults to `60 * 60` (3600 s), with a comment saying seconds. The API schema defaults to `600`.
- **Snooze**: no lookback window. It is bounded only by `f.expiration`, an absolute timestamp. Matching queries all of the signal's instances with no time bound.

**Problem with the unit change**

The UI still treats the value as minutes. `SignalFilterCreateDialog.vue:56` is labelled "Window (minutes)" and offers 5, 10, 15, 20 and 30 (line 196). It sends those numbers unchanged. Since `917a0b7b`, a filter the user set to 10 minutes looks back 10 **seconds**, and the 5–30 options give 5–30 seconds. I haven't checked how many filters exist with these values, or the production effect.

The tests use `window=5` (`tests/signal/test_signal_service.py:455` and others). They create their instances within the same second, so they would pass under either unit. I haven't run them to confirm.

Smaller items: the `filter_signal` docstring still says "1-hour window", and the code no longer matches it.

I haven't changed any code.

----- next turn -----

Commit `917a0b7b` caused it. Before that commit, `filter_dedup` converted the filter window from minutes. The commit switched it to treat the value as seconds, so a 30-minute window became 30 seconds and the two GuardDuty instances ten minutes apart never grouped.

**Fix**
- `src/dispatch/signal/service.py`: the filter window is now converted from minutes, `_window_start(f.window * 60)`. Stored values are untouched, so existing filters work without edits.
- `src/dispatch/signal/models.py`: the column's Python default went from `60 * 60` to `60`, and the comment now says minutes. The old value would have meant 60 hours under the corrected unit.
- The `filter_signal` docstring said "1-hour window", which was already wrong. It now refers to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Regression test**
- `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It creates a prior instance ten minutes ago, adds a dedup filter with window 30, and expects the new instance to be deduplicated.
- It fails with the old line and passes with the fix.

**Verification**
- `python -m pytest tests/signal tests/case`: 58 passed, 1 skipped.
- `ruff check` passes on the changed signal files. The `ruff format --check` failures are in files I didn't touch (`test_signal_flow.py`, `test_signal_stats_service.py`, and a blank line in `models.py` around line 416).
- I didn't run the full test suite.

**Not changed, needs your decision**
- The API schema default is still `window: int | None = 600` in `src/dispatch/signal/models.py:282`. Under the minutes unit, that is 10 hours, so any API client that omits `window` gets a 10-hour dedup window. That was already the meaning before `917a0b7b`, so I left it alone. Changing it to 10 would change API behavior, so tell me if you want that.
- I haven't checked production filter rows, so I can't say how many filters the bug affected. Filters created through the UI have minutes stored, which is what the fix expects.

Nothing is committed.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, *refactor(signal): simplify snooze filter checks*). It changed the expired-filter check in `filter_snooze` from `continue` to `break`. When the first snooze filter on a signal has expired, the loop stops there and never reaches a valid filter after it. So the "Okta: Impossible travel" user's expired filter blocked the valid one.

**Fix**
- `src/dispatch/signal/service.py:763`: the expired check is back to `continue`, so the loop moves on to the next filter.

**Regression test**
- `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It sets up an expired snooze filter first and a valid one for 30 more days second, then expects a new instance for the same entity to be snoozed.
- I checked that it fails when the code uses `break` and passes with `continue`.

**Verification**
- `python -m pytest tests/signal tests/case`: 59 passed, 1 skipped.
- `ruff check` passes on the signal source and tests. `ruff format --check` passes on the two files I changed in this step.

Nothing is committed. Earlier in this batch I fixed the window unit in `917a0b7b`, and that fix is still in place.

----- next turn -----

**Reminders (Monday case close/stable reminders)**

- The Monday check was `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` returns 1 for Monday, and `calendar.MONDAY` is 0, so the check never matched. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved this check into `_is_reminder_day()`. It was deployed as `main-81d8ae42` on 2025-08-13 at 16:40 UTC.
- The logs confirm the timing. Case close reminders went out on Monday 2025-08-04 and Monday 2025-08-11, both before the deploy. The first missed Monday was 2025-08-18.
- The fix uses `date.today().weekday() == calendar.MONDAY`, with a regression test that fails on the old check. Nothing is committed.

**Evening TypeError**

- The close reminder job subtracted `case.triage_at` from the current time. For cases with no triage time, the subtraction raised `TypeError`. The per-case `try` logged it and skipped the case, so the job kept running. The error appeared every evening from 2025-07-28 to 2025-08-20.
- Cases with no `triage_at` most likely come from the Slack Re-open button, which sets the status without running the transition flow. I couldn't confirm which cases are affected because the logs have no case IDs.
- The job now counts from `created_at` when `triage_at` is missing. Two tests cover this. The Re-open button path still needs a decision from you.

**Deduplication and snooze regressions (same batch)**

- **Dedup windows:** `917a0b7b` (2025-08-14) switched the per-filter window from minutes to seconds, but the UI still sends minutes. A 30-minute window became 30 seconds. Fixed by converting minutes to seconds in code, so existing filters work unchanged. Regression test added.
- **Snooze:** `086dc910` (2025-08-07) changed the expired-filter check from `continue` to `break`, so a valid snooze filter after an expired one was never checked. Restored `continue`. Regression test added.
- The canary change (`a348bbd2`, 2025-05-29) is still in place and correct. Canary instances are excluded from dedup. Only the three commits above caused regressions.
- Default dedup window is 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Before `7a9fe810` it was hard-coded to 1 hour.

Test results: `python -m pytest tests/signal tests/case` gives 59 passed, 1 skipped. I did not run the full test suite. Everything above is uncommitted. The hashes listed are the commits that introduced the regressions.

```
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
```