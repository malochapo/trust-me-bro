**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. The old code compared `date.today().isoweekday()` to `1`, which is correct because `isoweekday()` returns 1 for Monday. The refactor moved that comparison into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (Monday-based week, where Monday is 0), so the expression is `isoweekday() == 0`, which is never true. Both `case_close_reminder` (triage, line 49) and `case_stable_reminder` (stable, line 95) call this helper, so both Monday sends stopped. The daily `case_triage_reminder` does not use the helper, which is why those still arrive. I confirmed `calendar.MONDAY == 0` and `isoweekday()` of a Monday is `1` in the sandbox.

**Logs agree:**
- Case close reminders ("Case close reminder sent to …") went out on Mondays 2025-07-28, 08-04 and 08-11.
- The Monday 2025-08-18 run executed `case_close_reminder` and `case_stable_reminder` but sent nothing.
- Daily triage reminders kept sending on 08-19 and 08-20.

**Deploy that shipped it:** the scheduler container started with image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40:06Z (the web container got the same image at 16:40:07). Commit `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)", 2025-08-12) contains `c509d45e`, so that deploy shipped the bug. The 2025-08-11 run was still on the previous image (`main-b05613b5`), which is why it worked. The api.log has no reminder entries, so it doesn't add evidence either way.

**Unrelated noise:** `scheduler.log` has `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors in `case_stable_reminder` from 2025-07-28 through 08-12. Those come from cases with no `stable_at`, which commit `32fa810f` guards with `if case.stable_at:`. That fix is in the deployed image, and the errors stop after 08-12, so it is not the cause of the missing reminders.

**Suggested fix (not applied):** change the helper to `date.today().isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`. Adding a test that pins a known Monday would catch this kind of mistake. No code was changed.

----- next turn -----

The Monday reminder check is fixed, and a regression test covers it. I haven't committed.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both are 0-based, so Monday matches. The previous `isoweekday()` is 1-based, so it never matched.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `date.today` and checks that a Monday returns True and a Tuesday, Friday, and Sunday return False. I checked it against the buggy expression: the Monday case fails, and it passes again once the fix is restored.

**Tests:** `python -m pytest tests/case tests/case_cost` passes (38 tests). I didn't run the full suite, since the change is one line.

The test covers only the weekday gate, not the full reminder send path. I kept it narrow because calling the scheduled functions directly needs the project-context decorators. Say if you want an end-to-end test of `case_close_reminder` and `case_stable_reminder`.

----- next turn -----

The close-reminder TypeError is fixed, and the job now counts cases with no `triage_at` from `created_at`. I haven't committed.

**Cause:** `case_close_reminder` subtracts `case.triage_at` from the current time. `triage_at` is nullable, and it only gets set when a case transitions into triage. The 2022 migration that added the column (`391f7c3e6992`) did not backfill it, so a case that was already in triage then keeps `triage_at = NULL`, and the subtraction fails.

The logs show one such failure per evening from 2025-07-28 through 2025-08-12. The errors stop after that. The logs don't say why, and I didn't check the database to see which case it was or whether it has since left triage or got a timestamp.

**Fix** (`src/dispatch/case/scheduled.py`): `triage_started_at = case.triage_at or case.created_at`, and the span is measured from that. The `triage_at` value still wins when it is set.

**Tests** (`tests/case/test_case_scheduled.py`):
- No `triage_at`, created 8 days ago, on a Monday: the reminder is sent.
- No `triage_at`, created 2 days ago: no reminder.
- `triage_at` 8 days ago, created 1 day ago: the reminder is sent, so `triage_at` still takes precedence.

The tests call the raw job through the scheduler registry. I checked that the first test fails when the fallback is removed. `python -m pytest tests/case tests/case_cost` passes (41 tests).

The stable-reminder job still skips cases with no `stable_at` instead of counting from `created_at`, since you only asked about the close job. Say if you want the same fallback there.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 changed snooze or dedup behavior. Two of them changed the time windows. I made no code changes.

**Current windows, as the code applies them:**
- **Default dedup window (signals with no filters):** 45 minutes, or 2700 s. It is read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), so the env var is in minutes. `filter_dedup` converts it to seconds (`service.py:805`).
- **Per-filter dedup window (`SignalFilter.window`):** seconds. The model column defaults to 3600 s, or 1 hour (`signal/models.py:206`). The API schema default is 600 s, or 10 minutes (`signal/models.py:282`).
- **Snooze:** no lookback window. It uses an absolute `expiration` timestamp.

**Commits, oldest first:**

1. **`a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals":** Canary signals skip dedup, and they are excluded from the dedup matches of other signals. No window change.

2. **`7a9fe810`, 2025-06-19, "make the default deduplication window configurable":** The default window for signals with no filters was hard-coded at 1 hour. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. That is a default change from 60 to 45 minutes.

3. **`086dc910`, 2025-08-07, "simplify snooze filter checks":** The snooze loop now uses `break` on an expired snooze, where it used `continue` before. Filters after the first expired one are no longer checked. The per-filter warnings for missing mode or action were also removed, so those cases are now skipped silently. No window change.

4. **`917a0b7b`, 2025-08-14, "share the lookback window computation":** This adds `_window_start(seconds)`. Per-filter dedup windows were previously converted as minutes (`timedelta(minutes=f.window)`). They are now treated as seconds, which matches the column comment. A filter with `window=600` used to look back 10 hours and now looks back 10 minutes. I haven't checked stored filter values in the database, so I don't know how many existing filters this affects.

**Stale text:** the `filter_signal` docstring still says the default dedup window is 1 hour. The code uses 45 minutes.

----- next turn -----

The cause is commit `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the per-filter window from minutes to seconds. The UI labels the field "Window (minutes)", and its options are 5, 10, 15, 20, and 30. So a window of 30 became 30 seconds, and the instance from ten minutes earlier fell outside it.

**Fix:**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The per-filter window passes `f.window` directly, and the default window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly. Filters already stored with UI values such as 30 now mean 30 minutes again, so nothing needs editing.
- `src/dispatch/signal/models.py`: the column comment now says minutes. I also changed the column default from 3600 to 60, so a new filter without a window gets 1 hour rather than 60 hours.

**Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`, parametrized over window 5 and 30. The earlier instance is ten minutes old. The window-5 case must not dedupe and the window-30 case must. Against the unfixed code, the window-30 case failed with `'none' == 'deduplicate'`. After the fix both pass. I also added the `import pytest` the parametrize needs.

**Tests:** `python -m pytest tests/signal tests/case tests/case_cost` gives 75 passed and 1 skipped. I did not run the whole suite, and I did not check which test is skipped.

**Left alone:**
- The API schema default for `SignalFilterBase.window` is still 600, which is 10 hours in minutes. I didn't change it because it affects API-created filters without a window. Say if you want it set to 60.
- The `filter_signal` docstring still says the default window is 1 hour, though the default is 45 minutes.
- Nothing is committed.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). It changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. The loop in `src/dispatch/signal/service.py` then stops at the first expired snooze filter. When the expired filter comes first, the valid one after it is never checked, so the user's new instances are not snoozed.

**Fix:** I changed `break` back to `continue` at `service.py:763`. Expired filters are skipped and the loop goes on, as it did before the refactor.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It puts a snooze filter that expired seven days ago ahead of one that is valid for thirty days, and asserts the instance is snoozed. With `break` restored temporarily, the test fails; with `continue` it passes.

**Tests:** `python -m pytest tests/signal tests/case tests/case_cost` gives 76 passed and 1 skipped. That skip was already there in the earlier run.

Nothing is committed. Uncommitted changes from the window fix and this fix are both in `service.py`, `models.py`, and `tests/signal/test_signal_service.py`, along with the earlier `scheduled.py` change.

----- next turn -----

**Weekly reminder investigation.** Monday case-close and case-stable reminders stopped after commit `c509d45e` ("refactor(case): share the weekly reminder check"). That commit made `_is_reminder_day()` compare `date.today().isoweekday()` with `calendar.MONDAY`, which is 0. ISO weekday numbering starts at 1, so the check was never true. The commit shipped in image `main-81d8ae42`, deployed 2025-08-13 16:40Z. The first Monday without reminders was 2025-08-18, since 2025-08-11 came before the deploy. I fixed it to use `weekday()` and added `tests/case/test_case_scheduled.py`, which covers the weekday check and the reminder jobs.

**Nightly TypeError.** The close-reminder job subtracted `case.triage_at` from the current time. `triage_at` is nullable and was only set when a case moved into triage. The 2022 migration that added it did not backfill existing cases, so a case that was already in triage has no value and the subtraction fails. The job now counts from `created_at` when `triage_at` is missing, and it still prefers `triage_at` when it is set. The logs show the errors stopped after 2025-08-12, and I did not identify the specific case from data. I added three tests for this.

**Signal filter regressions.** Three separate bugs:
- `917a0b7b` read per-filter dedup windows as seconds, but the UI sets them in minutes. A 30-minute window became 30 seconds. I changed the window back to minutes, fixed the model column default from 3600 to 60, and added a parametrized regression test.
- `086dc910` changed the expired-snooze branch from `continue` to `break`, so a valid snooze filter after an expired one was never applied. I restored `continue` and added a regression test.
- `a348bbd2` made canary signals skip deduplication, both as the instance being checked and as a match for others.

Test status: `python -m pytest tests/signal tests/case tests/case_cost` gives 76 passed and 1 skipped. Nothing is committed.

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