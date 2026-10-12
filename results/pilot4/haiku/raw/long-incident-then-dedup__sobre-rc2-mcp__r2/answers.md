**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") broke the Monday check. The new helper compares an ISO weekday to `calendar.MONDAY`, but those use different numbering:

- `src/dispatch/case/scheduled.py:31-33`:
  ```python
  def _is_reminder_day() -> bool:
      return date.today().isoweekday() == calendar.MONDAY
  ```
- `isoweekday()` returns 1 for Monday. `calendar.MONDAY` is 0 (I confirmed both in Python). So `_is_reminder_day()` is always False, and the weekly branch never runs.
- The original code was `date.today().isoweekday() == 1`, which was correct. The refactor swapped the literal `1` for `calendar.MONDAY` and changed the result.
- Both weekly sends are gated on this helper: `case_close_reminder` (triage, line 49) and `case_stable_reminder` (stable, line 95). The daily `case_triage_reminder` doesn't use it, which matches what you're seeing: daily triage reminders still go out, weekly ones don't.
- It fails silently. No exception is raised, so nothing shows up in the logs.

**Deploy that shipped it:** `81d8ae42` ("fix(case): exclude resolved_by in update", #6183), which contains `c509d45e` as an ancestor. It went out as image `registry.example.com/dispatch:main-81d8ae42`, and the scheduler and web pods started on it at **2025-08-13T16:40:06Z** (`scheduler.log`/`api.log`, kubelet lines). The previous image, `main-b05613b5`, started on 2025-07-30 and doesn't contain `c509d45e`.

**Log evidence:**
- Before the deploy, Monday runs (2025-08-04 and 2025-08-11) show extra per-case activity in `case_close_reminder`. Those are the Mondays the weekly reminders were still firing.
- The first Monday after the deploy is 2025-08-18. The logs have no send records, so that part is inferred from the code and the timing rather than shown directly.

**Side note:** the scheduler logged `unsupported operand type(s) ... 'NoneType'` from `case_stable_reminder` every day from 07-28 until the deploy. That was a separate bug, fixed by `32fa810f` (#6179, "not all cases have a stable_at date"). It shipped in the same `81d8ae42` deploy, so it's now resolved too.

No code was changed. The likely fix is to compare against the same 1-based value (`date.today().isoweekday() == 1`) or to use `date.today().weekday() == calendar.MONDAY`, which is 0-based. I haven't checked whether any test covers `_is_reminder_day`.

----- next turn -----

The weekly reminders are fixed, and the regression test fails on the old code and passes on the new.

**Fix** (`src/dispatch/case/scheduled.py:33`): the helper compared `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It now uses `date.today().weekday() == calendar.MONDAY`, which uses the same 0-based numbering on both sides.

**Regression tests** (new file `tests/case/test_case_scheduled.py`, 11 tests):
- `_is_reminder_day` returns True on Monday 2025-08-18 and False on each other day of that week. The Monday case is the one that failed before the fix.
- `case_close_reminder` (triage) and `case_stable_reminder` (stable) each send for an 8-day-old case on a Monday, and skip on a Tuesday. The two Monday tests fail on the old code, and the Tuesday tests guard against the check being always true.
- The tests call the undecorated task functions with `get_all_by_status` and `send_case_close_reminder` mocked, so they don't need the database.

**Results:**
- New test file: 11 passed, and 3 failed before the fix (the Monday-positive cases).
- `python -m pytest tests/case`: 26 passed.
- `ruff check` and `ruff format --check` pass on both changed files.

I ran only the `tests/case` directory, not the full suite. The commit is not made.

----- next turn -----

The close reminder now falls back to `created_at` when `triage_at` is missing, and it has two new tests. The `tests/case` directory passes (28 tests). Nothing is committed.

**Cause of the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at = NULL`, so the subtraction raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The exception is caught per case and logged, so the job goes on, but that case never gets its reminder. The log shows this every evening from 2025-08-16 (40 occurrences through 08-20).

`triage_at` is set only in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), which runs on the transitions into triage. Any case that reaches triage without that flow keeps a null value. I couldn't confirm which path produced these particular cases: the logs don't name them, and there are no "Unexpected previous state" warnings in either log. The `(_, CaseStatus.triage)` branch in `flows.py` that logs that warning doesn't set `triage_at`, so it's a candidate, but I haven't tied it to these cases.

**Fix** (`src/dispatch/case/scheduled.py:47-48`):
```python
# some cases never got a triage_at, so we count from when they were created
span = datetime.utcnow() - (case.triage_at or case.created_at)
```

**Tests** (added to `tests/case/test_case_scheduled.py`):
- A triage case with `triage_at=None` and created 8 days ago gets a reminder on a Monday. This fails without the fallback.
- A triage case with `triage_at=None` and created 2 days ago does not get one.

Both tests go through the undecorated task, the same as the earlier tests.

**Not changed:** `case_stable_reminder` has the same kind of gap, but it skips stable cases with no `stable_at` instead of falling back. You only asked about the close reminder, so I left it. Say if you want the same fallback there.

----- next turn -----



----- next turn -----

Six commits since 2025-05-22 changed snooze or dedup behavior or their windows. None of the changes is in the working tree; I only read history.

**Current windows, as the code applies them**
- **Default dedup window (filters with no rules):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes** (2,700 s). It is read in minutes and converted to seconds (`src/dispatch/config.py:95`, `src/dispatch/signal/service.py:805`).
- **Per-filter dedup window:** `SignalFilter.window`, stored and read in **seconds**. The schema default is **600 s** (10 min) (`src/dispatch/signal/models.py:282`). The DB column default is **3600 s** (1 h) (`models.py:206`).
- **Snooze:** no time window. A snooze lasts until `SignalFilter.expiration`.

**Commits, oldest first**

1. **`a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals (#6026)".** Canary instances skip dedup entirely (`filter_dedup` returns early). They are also excluded from the lookups for both the default and the per-filter paths. No window value changed.

2. **`7a9fe810`, 2025-06-19, "make the default deduplication window configurable".** The default-path window was hard-coded to `timedelta(hours=1)`. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes. The docstring in `filter_dedup` still says "1-hour window".

3. **`086dc910`, 2025-08-07, "refactor(signal): simplify snooze filter checks".** This was meant as a refactor, but it changed behavior in `filter_snooze`:
   - When a snooze filter's expiration has passed, the code now `break`s instead of `continue`s. Any later active snooze filters on the signal are no longer checked.
   - The warnings for a missing mode or action were removed. The model's `mode` and `action` columns are non-nullable, so the practical effect is small.

4. **`917a0b7b`, 2025-08-14, "refactor(signal): share the lookback window computation".** This changed the per-filter window's unit. The old code computed `timedelta(minutes=f.window)`. The new code uses `_window_start(f.window)`, which is `timedelta(seconds=...)`. A filter's `window` is therefore now a number of seconds, not minutes. A stored value of 600 was 10 hours before this commit and is 10 minutes now. The default-path result is unchanged, because it still resolves to 45 minutes.

Commit 4 is the one that changes results for existing per-filter dedup rules, and it is the one to check against any rules that were created with minute-based values.

I did not run the tests, and I did not check whether these commits reached production or what the stored `window` values are in the database.

----- next turn -----

The cause was commit `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the per-filter window from minutes to seconds. A filter set to 30 in the UI became a 30-second window, so two instances ten minutes apart fell outside it and each opened a case.

**Fix** (`src/dispatch/signal/service.py`)
- `_window_start` takes minutes again, and both callers pass minutes: the per-filter window (`f.window`) and the default `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- The UI's "Window (minutes)" field sends the raw value, so existing filters work with no data change. A filter saved as 30 is again a 30-minute window.
- I corrected the unit comments in `models.py` and `service.py`. The default-path result is the same as before, since it still resolves to 45 minutes.

**Regression test** (`tests/signal/test_signal_service.py`, `test_filter_actions_deduplicate_window_is_in_minutes`)
- A deduplicate filter with `window=30`, an existing instance with a case created 10 minutes ago, and a new instance. The new instance must be deduplicated onto that case.
- It fails on the code before this fix and passes after it.

**Results:** `python -m pytest tests/signal` gives 33 passed and 1 skipped. I did not run the full suite. `ruff format --check` flags `models.py:416`, but that is in code I didn't touch, and it was already flagged before my edits.

**Not changed, needs your decision:** two defaults still use values written for seconds, so under minute units they are now much longer than intended:
- `SignalFilterBase.window` defaults to 600 (`models.py:282`), which is now 10 hours.
- The `SignalFilter.window` column default is 3600 (`models.py:206`), which is now 60 hours.

Changing either alters how filters created without a window behave. That is a separate decision from this fix, so I left them alone. The `filter_dedup` docstring still says "1-hour window" for the default path, which is out of date (the default is 45 minutes).

----- next turn -----

The cause was commit `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). It changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. An expired filter listed before a valid one therefore ended the loop, so the valid filter was never checked. New instances for that user matched no snooze and were not snoozed.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): an expired snooze is skipped with `continue`, so the loop moves on to the remaining filters. This restores the behavior from before `086dc910`.

**Regression test** (`tests/signal/test_signal_service.py`, `test_filter_actions_snooze_after_expired_snooze`): an expired snooze is listed first, a valid one for the same entity second, and the instance must be snoozed. It fails on the old code and passes with the fix.

**Results:** `python -m pytest tests/signal` gives 34 passed and 1 skipped. `ruff check` passes on the signal code and tests.

`086dc910` also removed the warning logs for a filter with no mode or no action. I did not restore those. The model's `mode` and `action` columns are non-nullable, so they can't be missing, and the warnings were not part of this bug. Say if you want them back.

----- next turn -----

Here's the recap for both investigations. The fixes are uncommitted in the working tree.

**Investigation 1: missing Monday case reminders**
- Long-running triage and stable cases stopped getting their weekly reminders. The daily triage reminders kept arriving.
- Cause: `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") introduced this when it moved the check into the helper. Before that, the code compared `isoweekday()` with `1`, which was correct.
- Shipped in image `main-81d8ae42`, which started on the scheduler at 2025-08-13 16:40 and contains `c509d45e`.
- Last Monday with case reminders in the logs was 2025-08-11. The first missed Monday was 2025-08-18, when only the incident close reminder was logged.
- Fix: `weekday() == calendar.MONDAY`. Regression tests in `tests/case/test_case_scheduled.py` fail on the old code.

**Investigation 2: evening TypeError in the case close reminder**
- Cause: some triage cases have no `triage_at`, so `datetime.utcnow() - case.triage_at` raised `TypeError`. The error was caught per case, so the job continued but those cases got no reminder. It first appeared 2025-08-16.
- Source of the NULL values is not confirmed: `triage_at` is only set by `case_triage_status_flow`, and the logs don't name the affected cases.
- Fix: `span = datetime.utcnow() - (case.triage_at or case.created_at)`. Two tests were added.
- Not changed: `case_stable_reminder` still skips stable cases with no `stable_at`.

**Signal bugs (also from this batch of commits)**
- Deduplication windows: commit `917a0b7b` changed the per-filter window from minutes to seconds, so a window of 30 became 30 seconds. Fixed in `src/dispatch/signal/service.py`, with a regression test.
- Snoozing: commit `086dc910` changed an expired snooze from `continue` to `break`, which stopped checking later snooze filters. Fixed, with a regression test.
- Canary signals: commit `a348bbd2` made canary instances skip deduplication.

**Open items:** the `SignalFilterBase.window` default of 600 and the `SignalFilter.window` column default of 3600 were written for seconds. They are now read as minutes, so those defaults are much longer than intended. I left them unchanged.

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