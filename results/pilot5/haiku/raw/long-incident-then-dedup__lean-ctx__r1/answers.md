**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:33` compares ISO weekday to the wrong constant:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Monday is the first day of the `calendar` module's week; `/usr/lib/python3.10/calendar.py:99` defines `(MONDAY, ..., SUNDAY) = range(7)`). So the check is never true, and both `case_close_reminder` and `case_stable_reminder` skip every case on every day. The triage reminder has no weekday gate, which is why the daily triage reminders kept arriving.

**The commit:** `c509d45e` "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()` and used `calendar.MONDAY` in place of the literal `1`. The refactor looks like a no-op, but it changed the value. The untouched weekday check in `src/dispatch/incident/scheduled.py:229` still uses `== 1`, which is correct.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, started 2025-08-13 16:40 UTC on both the scheduler and web pods (`scheduler.log` and `api.log`). `c509d45e` is an ancestor of `81d8ae42`. The previous deploy, `main-b05613b5` (2025-07-30), does not contain it.

**Log evidence:**
- Case close reminders went out on Monday 2025-08-04 (7 sends) and Monday 2025-08-11 (6 sends), both under the old build.
- After the deploy, the only Monday in range with no sends is 2025-08-18. The one "close reminder" line that day is an incident reminder (`incident/messaging.py`), not a case one.
- Triage reminders continue daily through 2025-08-20.

The `NoneType` tracebacks in `scheduler.log` (2025-07-28 to 2025-08-15) are a separate, earlier bug. They came from `case.stable_at` / `case.triage_at` being `None`, and commit `32fa810f` fixed them on 08-11. They are not related to the missing reminders.

I haven't changed any code. The fix is to compare against 1, or to use `calendar.MONDAY` consistently with `.weekday()` (which is 0-based), not `.isoweekday()`. Adding a test for `_is_reminder_day()` on a Monday would catch this.

----- next turn -----

The weekly reminders are fixed and a regression test is in place. I haven't committed anything.

**Fix:** `src/dispatch/case/scheduled.py:33` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so the comparison is correct. I chose this over changing the constant to `1` so the check uses the `calendar` constant the way the rest of the module does.

**Regression test:** `tests/case/test_case_scheduled.py` checks `_is_reminder_day()` for Monday 2025-08-11 through Sunday 2025-08-17, with `date.today()` mocked. I ran it against the old code: the Monday case fails with `assert False is True`. With the fix, all 7 cases pass.

**Full suite** (`python -m pytest`, PostgreSQL running locally): 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way with my source change stashed, so they predate this fix and I left them alone.

The reminder path itself (sending the close and stable reminders) is not covered end to end; the test covers only the day check.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and there's a regression test for it. Nothing is committed.

**Cause:** `case_close_reminder` (`src/dispatch/case/scheduled.py`) computes `datetime.utcnow() - case.triage_at`. Some cases in `triage` status have `triage_at = NULL`, so Python raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. `triage_at` is only written by `case_triage_status_flow` (`flows.py:595`). The Slack handlers that set `case.status = CaseStatus.triage` directly (`interactive.py:1312`, `:1427`, `:2246`) can bypass it. I didn't trace which production path created the NULL rows. The per-case `try` logs the error and moves on, so the other cases still get their reminders, but these cases never do. The log shows 40 of these errors across the period; the close job's version fails at line 55 in the deployed build, and the stable job's `NoneType` errors stopped on 08-13, when the deploy added its `if case.stable_at:` guard.

**Fix:** `span = datetime.utcnow() - (case.triage_at or case.created_at)`, with a one-line comment explaining the fallback.

**Test:** `tests/case/test_case_scheduled.py` gained a parametrized test with four cases:
- No `triage_at`, created 8 days ago: sent.
- No `triage_at`, created 3 days ago: not sent.
- `triage_at` 2 days ago, created 30 days ago: not sent, so `triage_at` still counts over `created_at`.
- `triage_at` 8 days ago, created 30 days ago: sent.

The job is reached through `scheduler.registered_tasks`, because `@scheduler.add` returns `None`. I confirmed the NULL-`triage_at` case fails without the fix and passes with it.

**Results:** `python -m pytest`: 370 passed, 4 skipped, 8 failed. The 8 failures are the same pre-existing ones as before (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`); I confirmed they fail without my changes too.

Things you may want to know:
- `CaseFactory` has `status = "New"` in its `Params`, which silently overrides a `status=` kwarg. The test sets the status after creating the case.
- `case_stable_reminder` has the same kind of gap: its `if case.stable_at:` guard skips cases with no `stable_at` instead of falling back to a timestamp. You asked only about the close job, so I left it alone. Say if you want the same fallback there.

----- next turn -----



----- next turn -----

Since 2025-05-22, four commits changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or the windows it uses. I made no code changes.

**1. `a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals (#6026)"**
- Canary signal instances skip deduplication, and canary instances are excluded when looking for a match. No time window is involved.

**2. `7a9fe810`, 2025-06-19, "feat(signal): make the default deduplication window configurable"**
- Signals with no deduplication filters used a hard-coded 1 hour before this commit.
- The window now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), in minutes. The default is **45 minutes**, which is 2700 seconds.

**3. `086dc910`, 2025-08-07, "refactor(signal): simplify snooze filter checks"**
- The mode and action checks were merged into one condition, and the "no mode" and "no action" warnings were removed.
- Behavior change: an expired snooze filter used to `continue` to the next filter. It now `break`s, so later snooze filters are not checked. The commit message doesn't mention this.
- Snooze has no time window. It depends on the filter's `expiration` timestamp, and a snooze with no expiration is skipped with a warning.

**4. `917a0b7b`, 2025-08-14, "refactor(signal): share the lookback window computation"**
- Behavior change: a deduplication filter's `window` used to be read as **minutes** (`timedelta(minutes=f.window)`). It is now read as **seconds** through the new `_window_start()` helper (`src/dispatch/signal/service.py:784`).
- A filter window is now 60 times shorter than before. The model comment says seconds (`src/dispatch/signal/models.py:207-208`), so the old code was the outlier, but the change is not in the commit message.
- Values as the code applies them today:
  - `SignalFilter.window` column default: 3600 seconds (1 hour).
  - `SignalFilterBase.window` schema default: 600 seconds (10 minutes).

**Current windows, for reference**
- Deduplication filter: `f.window` seconds, looking back from now.
- Signals with no deduplication filter: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` minutes (default 45).
- Snooze: no lookback. Active until `expiration`.

**Not checked**
- I did not check the production rows for existing `window` values, so I can't say whether any stored filter windows are now effectively 60 times shorter.
- The `filter_signal` docstring (`service.py:873`) still says "1-hour window", which is stale.
- The other commits that mention snooze or dedup (`90f73fe2`, `5e136d7b`, `01c28ff0`, `dee1699d`, `200cd428`) only touch UI labels or unrelated fields.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed how a deduplication filter's `window` is read, from minutes to seconds. The UI labels the field "Window (minutes)" and offers 5–30, so a window of 30 was 30 minutes and is now 30 seconds. Two instances ten minutes apart fall outside a 30-second window, so each opened a case. The other commits in my earlier list don't touch filter windows (`7a9fe810` only changed the default window for signals with no filter, and `086dc910` only changed snooze handling).

**Fix** (`src/dispatch/signal/service.py`)
- `_window_start` takes minutes again, so `f.window` is used as the UI sets it. Existing filters keep their stored values and need no edits.
- The default-window path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, since the helper now takes minutes. Its effective value is unchanged.
- Comments updated to say minutes.
- `src/dispatch/signal/models.py`: the column comment now says minutes.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_dedup_window_is_in_minutes`, parametrized over two cases:
- Earlier instance 10 minutes ago, window 30: deduplicated.
- Earlier instance 45 minutes ago, window 30: not deduplicated.

The 10-minute case fails on the pre-fix `service.py` and passes with the fix.

**Test results:** `python -m pytest`: 372 passed, 4 skipped, 8 failed. Before this change it was 370 passed, so the two new tests pass. The 8 failures are the same pre-existing ones as before (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`).

**Not changed**
- The column default `window = 60 * 60` (`models.py`) and the API schema default `window = 600` are now read as minutes (60 hours and 10 hours). Before 08-14 they were also read as minutes, so this isn't new. The column comment used to say "default to 1 hour", so the intent may have been 60 minutes. I left the defaults alone because changing them would affect filters created without a window. Say if you want that changed.
- I didn't check production rows to see whether any filters were saved through a path other than the UI. The UI always sends minutes.
- Nothing is committed.

----- next turn -----

The cause is `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). In `filter_snooze`, it changed the expired-snooze branch from `continue` to `break`. The loop over a signal's filters stopped at the first expired snooze, so a valid snooze listed after it was never checked. The "Okta: Impossible travel" user got no snooze because their expired filter came first.

**Fix** (`src/dispatch/signal/service.py:762-763`): an expired snooze is skipped with `continue`, so the loop checks the remaining filters.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_snooze_skips_expired_snooze_filter`. It creates an expired snooze filter (7 days ago) listed before a valid one (30 days ahead) on the same entity, then asserts the instance is snoozed.
- With the fix, it passes.
- With `break` restored, it fails.

**Test results:** `python -m pytest`: 373 passed, 4 skipped, 8 failed. The 8 failures are the same pre-existing ones as before (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`).

Nothing is committed. Two things remain from earlier work in this session:
- The commit `917a0b7b` fix (window units) is also still uncommitted.
- Two other changes from the batch are still in the code. `917a0b7b` is fixed, but `086dc910`'s other change, which removed the "no mode" and "no action" warnings, is not reverted. It has no visible effect, because those fields can't be empty in the schema.

----- next turn -----

**Weekly reminder and case close TypeError (today's first two investigations)**

- **Missing weekly reminders:** Since the 2025-08-13 deploy, the weekly close and stable reminders have not gone out. The cause is in `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0), so the check never matched. The bug was introduced by `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") and shipped in `main-81d8ae42`, which started on 2025-08-13 at 16:40 according to the scheduler log. The fix uses `date.today().weekday()`. A parametrized test covers the Monday/Sunday boundary.
- **Nightly TypeError:** The close job computed `datetime.utcnow() - case.triage_at`. Some cases were in `triage` status with `triage_at` NULL, because a few Slack paths set the status directly and skip the flow that stamps `triage_at`. The fix counts from `created_at` when `triage_at` is missing, and a parametrized test covers that.

**Deduplication, snoozing, and the default window (second batch of reports)**

- **Deduplication windows:** `917a0b7b` (2025-08-14) changed how a filter's window is read, from minutes to seconds. The UI sets windows in minutes, so a window of 30 became 30 seconds, and instances ten minutes apart opened separate cases. The helper now takes minutes again, and a regression test covers the 10- and 45-minute cases.
- **Snoozing:** `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired snooze stopped the loop, so a valid snooze listed after it was never checked. The branch is back to `continue`, and a regression test covers it.
- **Canary signals:** `a348bbd2` (2025-05-29, "fix(signal): don't dedup on canary signals") is the change to how canary signals are deduplicated. It skips them and excludes them as matches. I didn't change it.
- **Default window:** Signals without any filter are grouped over 45 minutes. Before `7a9fe810` (2025-06-19) it was a fixed 1 hour. The value comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which is in minutes.

**Status:** Nothing is committed. The full suite is 373 passed, 4 skipped, and 8 failed. The 8 failures predate this work (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`). Not yet done: the stable-reminder path still has no `created_at` fallback, and the column default `window = 60 * 60` is now read as 60 hours. I flagged both earlier.

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