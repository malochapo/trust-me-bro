**Root cause:** the weekly Monday check in `src/dispatch/case/scheduled.py` compares against `calendar.MONDAY`, which is `0`, but `date.today().isoweekday()` returns `1` on Mondays. The check is therefore never true, so the weekly close and stable reminders never send. The daily triage reminder has no weekday check, so it still goes out.

**Commit that introduced it:** `c509d45e` "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). It replaced the working `date.today().isoweekday() == 1` with `_is_reminder_day()`, which returns `date.today().isoweekday() == calendar.MONDAY`. The bug is still at HEAD (line 33 of `src/dispatch/case/scheduled.py`).

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which is commit `81d8ae42` ("fix(case): exclude resolved_by in update", 2025-08-12). `c509d45e` is an ancestor of it. It started on the scheduler at 2025-08-13 16:40:06 UTC (`scheduler-mhtsgqwwx-q5q2n`), and the web pod started the same minute.

**Evidence from the logs:**
- Monday 2025-08-11, before the deploy (image `main-b05613b5`): 5 "Case close reminder sent" lines, and the job ran for 1.3s.
- Monday 2025-08-18, the first Monday after the deploy: the close and stable jobs ran and sent nothing. The job took 0.045s, the same as the non-Monday runs from 08-12 to 08-17 (about 0.03–0.05s each, no sends).
- Triage reminders kept sending daily, which matches the report.

I checked the Python behaviour directly: `calendar.MONDAY` is `0`, and 2025-08-18 has `isoweekday() == 1`, so the comparison is `False`.

**Separate issue, not the cause:** `case_close_reminder` still does `datetime.utcnow() - case.triage_at` with no `None` guard, so every day it logs a `TypeError` for cases in triage with no `triage_at`. Each case is in its own try block, so other cases still process. The stable path got a guard in `32fa810f` (2025-08-11), but the close path did not.

**Caveat:** the traceback line numbers in the logs don't match this checkout, so I matched the deploy by timestamp and commit ancestry rather than by line numbers.

No code was changed. For the fix, I'd suggest comparing against `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based like `calendar`), or using `isoweekday() == 1`, plus a `triage_at` guard on the close path. I'd also add a test that pins Monday behaviour, since none exists for it.

----- next turn -----

The reminders fix is in, with a regression test. I haven't committed anything.

**The fix** is one line in `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar`, so the two now agree.

**The regression test** is in a new file, `tests/case/test_case_scheduled.py`. It has three groups:
- `_is_reminder_day()` returns True only on Monday, checked for all seven days.
- The close and stable jobs send a reminder for an 8-day-old case on a Monday.
- The same jobs send nothing on a Tuesday.

The jobs are looked up by name in `scheduler.registered_tasks`, so the test runs the same callable the scheduler runs. I checked that the test catches the bug. With the old `isoweekday() == calendar.MONDAY` line put back, three tests fail, including both Monday reminder tests. With the fix in place, all 11 pass.

**Results:**
- `python -m pytest tests/case` passes: 26 tests, including the 11 new ones, against the local PostgreSQL.
- `ruff check` and `ruff format --check` pass on both files.
- I didn't run the full suite, only `tests/case`.

I left out the separate `None` guard on `triage_at` in `case_close_reminder`. It only logs an error per affected case and doesn't block other cases. It's a small change if you want it in the same commit.

----- next turn -----

The close reminder job now counts from `created_at` when `triage_at` is missing, and the TypeError is gone. Nothing is committed.

**What causes the TypeError:** the job loads every case in triage and subtracts `case.triage_at` from `utcnow()`. Some triage cases have `triage_at` set to NULL, and the subtraction raises. The per-case `try` catches it and logs it, so the other cases still run, but each evening the job logs one error per affected case.

`triage_at` is only set when a case moves into triage through `case_triage_status_flow` (New→Triage and Closed→Triage in `src/dispatch/case/flows.py`). Some code paths set the status to triage without calling that flow. The reopen button in `src/dispatch/plugins/dispatch_slack/case/interactive.py` (around line 1427) is one. Cases that predate `triage_at` tracking would also have it NULL. I can't tell from the logs which cases these are, since the errors don't include case IDs, and I don't have production DB access, so that part is unconfirmed.

**The change** is one line in `src/dispatch/case/scheduled.py`:
- `triaged_since = case.triage_at or case.created_at` is used as the count-from time.
- Cases with `triage_at` set behave as before.

**Tests**, added to `tests/case/test_case_scheduled.py`:
- A case with no `triage_at` and `created_at` 8 days ago gets a reminder on Monday. This test fails without the fallback.
- A case with no `triage_at` and a recent `created_at` gets no reminder.
- A case with a recent `triage_at` and an old `created_at` gets no reminder, so `triage_at` still takes priority.

`python -m pytest tests/case` passes: 29 tests against the local PostgreSQL. `ruff check` and `ruff format --check` pass.

I didn't change the stable reminder. It already skips cases with no `stable_at` and doesn't log an error for them. If you want those cases to count from `created_at` too, it's the same one-line change there.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or deduplication. Two of them change behavior in ways their messages don't mention. I didn't change any code.

**Commits, oldest first**

1. **`a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals".** Canary instances are no longer deduplicated, and they are excluded as dedup targets for other instances. Both the default and the filter-based paths are affected. No window changed.

2. **`7a9fe810`, 2025-06-19, "make the default deduplication window configurable".** The default window for signals with no dedup filter was hard-coded at 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), default **45 minutes**. The window is applied as `minutes * 60` seconds.

3. **`086dc910`, 2025-08-07, "refactor(signal): simplify snooze filter checks".** Two behavior changes sit inside a refactor:
   - An expired snooze filter used to `continue` to the next filter. It now `break`s out of the loop, so later active snooze filters are never checked. A signal that a later filter would have snoozed is no longer snoozed.
   - The warnings for a filter with no mode or no action were dropped, so those filters are now skipped silently.
   
   Snooze has no lookback window. A snooze filter is active until its `expiration` time, compared in UTC.

4. **`917a0b7b`, 2025-08-14, "refactor(signal): share the lookback window computation".** Before this commit, a filter's `window` was applied as `timedelta(minutes=f.window)`. The column stores seconds (`src/dispatch/signal/models.py:206`, comment "number of seconds"), so every stored window was read as 60 times too long. This commit makes it seconds (`filter_dedup`, `src/dispatch/signal/service.py:845-846`). Existing custom dedup filters now look back 60 times less far than before. For example, a stored window of 3600 used to mean 60 hours and now means 1 hour. The commit message doesn't mention this change.

**Windows as the code applies them today**

- **Snooze:** no lookback window. The filter applies while `expiration` is in the future.
- **Default dedup** (signal has no filters): **45 minutes**, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It matches the most recent instance created in that window that already has a case, regardless of entities, and skips canaries.
- **Filter dedup:** `f.window` in **seconds**. The schema default is **600 seconds (10 minutes)** (`models.py:282`). The column default is 3600 seconds (1 hour), but the schema default is what applies to filters created through the API.

**Stale comment:** the `filter_signal` docstring still says the default dedup is a 1-hour window. It is 45 minutes now.

I also checked the other commits that matched the keywords (`5e136d7b`, `90f73fe2`, `01c28ff0`, `dee1699d`, `d7271bfa`). They are UI or unrelated changes and don't affect this logic.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the filter window from minutes to seconds. A 30-minute window became 30 seconds, so the two instances ten minutes apart didn't group. I haven't committed anything.

**Why minutes is the right unit:** the UI labels the field "Window (minutes)" and offers 5–30. The code read the stored value as minutes from 2023-04 (`9c523348`) until `917a0b7b`. The model comment still said "seconds", and the 2022 original code used seconds. Existing rows hold the minute values people entered, so restoring minutes means no filter has to be edited.

**Changes:**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again, and both dedup paths use it directly. The default path still uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (45 by default). I also corrected the `filter_signal` docstring, which still said 1 hour.
- `src/dispatch/signal/models.py`: the column comment now says minutes.
- `tests/signal/test_signal_service.py`: two tests. A 30-minute window groups two instances ten minutes apart, and a 5-minute window does not.

**Verification:**
- The 30-minute test fails with the old `service.py` and passes with the fix. The 5-minute test passes both ways.
- `python -m pytest tests/signal tests/case`: 63 passed, 1 skipped.
- Ruff check passes on the touched code. Several other test files were already unformatted before my changes, and I left them alone.

**Not changed, needs your decision:**
- The model defaults are `window = 60 * 60` and the API default is `600`. Under minute units these are 60 hours and 10 hours. These only apply when a filter is created without a window, and this unit has been the behavior since 2023-04. The column comment says "1 hour", so I'm not sure which value you want. Tell me and I'll change them.
- `086dc910` still changes the snooze loop from `continue` to `break` on an expired snooze filter, so later snooze filters aren't checked. This is a separate issue from the dedup window and I haven't touched it.

----- next turn -----

The cause is `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). In `filter_snooze`, the expired-filter branch changed from `continue` to `break`. When the expired filter came first in the list, the loop stopped there and the valid filter was never checked. The commit message doesn't mention this behavior change.

**Fix:** `src/dispatch/signal/service.py:763` is back to `continue`. The rest of the simplified check stays as it was.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter followed by a valid one for the same entity, and asserts the instance is snoozed. It fails with the `break` version and passes with the fix.

**Verification:** `python -m pytest tests/signal tests/case`: 64 passed, 1 skipped. Ruff check and format pass on the touched files.

Nothing is committed. The working tree also still has the earlier uncommitted changes: the weekday and `created_at` fallback in `src/dispatch/case/scheduled.py`, the window-unit fix in `src/dispatch/signal/service.py` and `models.py`, and the new tests.

----- next turn -----

**Investigation 1: weekly reminders not sent for long-running cases**

Weekly Monday reminders stopped after the 2025-08-13 deploy. The weekday check compared `date.isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0, so the check never matched. Daily triage reminders were not affected. Introduced by `c509d45e` on 2025-08-12 and shipped in image `main-81d8ae42` on 2025-08-13. The fix uses `weekday()` and has regression tests in `tests/case/test_case_scheduled.py`. The first missed Monday is 2025-08-18. That date comes from the deploy date and the code; I did not confirm it against send logs.

The same log stream showed a `TypeError` each evening from the case close reminder job. Cases in triage can have no `triage_at`, and the job subtracted it from the current time. The job now counts from `created_at` when `triage_at` is missing. Cases with `triage_at` behave as before. The root cause of the NULL `triage_at` is still unconfirmed. Two candidates are the Slack reopen path, which sets triage without the transition flow, and legacy rows. The logs have no case IDs and I had no production database access.

**Investigation 2: signal deduplication and snoozing**

- **Deduplication windows:** `917a0b7b` (2025-08-14) changed the filter window from minutes to seconds. The UI labels the field "Window (minutes)", so a 30-minute window became 30 seconds and instances ten minutes apart opened separate cases. The window is minutes again, and existing filters need no edits. Regression tests are in `tests/signal/test_signal_service.py`.
- **Snoozing:** `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired filter first in the list stopped the check, so a valid filter after it was never applied. Fixed back to `continue`, with a regression test.
- **Canary signals:** `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated and from being used as dedup targets.
- **Default grouping:** signals with no filter are grouped over a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It was a hard-coded 1 hour before `7a9fe810`.

Open items: the model defaults for `SignalFilter.window` (60 × 60 and 600) are still unchanged. Under minute units they mean 60 hours and 10 hours. I did not change them.

Nothing is committed. The uncommitted changes are the weekday and `created_at` fallback fixes in `src/dispatch/case/scheduled.py`, the window-unit and snooze fixes in `src/dispatch/signal/service.py` and `models.py`, and the new tests in `tests/case/test_case_scheduled.py` and `tests/signal/test_signal_service.py`.

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