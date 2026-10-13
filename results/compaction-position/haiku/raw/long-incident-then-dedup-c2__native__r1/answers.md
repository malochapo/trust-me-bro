**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`, which compares `date.today().isoweekday()` against `calendar.MONDAY`. Those two use different numbering. `isoweekday()` returns Monday as 1, but `calendar.MONDAY` is 0 (I confirmed both in Python). So the check is `isoweekday() == 0`, which is never true, and the weekly close and stable reminders never send. The old code compared against the literal `1`, which was correct.

The daily triage reminder doesn't use this check, so it still fires, which matches what you're seeing.

**Shipped in:** image `main-81d8ae42`, rolled out to both the scheduler and web pods on 2025-08-13 at about 16:40 UTC. `81d8ae42` is the head commit ("fix(case): exclude resolved_by in update (#6183)"). `c509d45e` is an ancestor of it, so it went out in that deploy.

**Log evidence:**
- Close and stable reminders were sent on Mondays 07-28, 08-04 and 08-11, which is before the deploy and matches the old `== 1` comparison.
- Monday 08-18 has no weekly sends, the first Monday after the deploy. The log has no later Mondays, so 08-25 is unconfirmed.
- Triage reminders were sent every day through 08-20, as you described.

**Separate problem, not the cause:** `case_close_reminder` logs a `TypeError` (datetime minus None) every day from 07-28 through 08-20. Some triage cases have no `triage_at`. The weekly check runs after the `triage_at` subtraction, so those cases error out before the Monday test. Commit `32fa810f` added a `stable_at` guard to the stable reminder but not the equivalent guard for `triage_at`. The errors are caught per case, so they don't stop other cases from being processed. The stable-reminder errors stopped after the 08-13 deploy.

**Suggested fix (not applied):** restore the `isoweekday()` comparison to 1, for example `date.today().isoweekday() == 1` or a named constant with value 1 and a comment that it's ISO. Add a `triage_at` guard in `case_close_reminder` like the one `32fa810f` added for `stable_at`. A regression test that patches the date to a Monday would catch the mismatch.

I didn't change any code.

----- next turn -----

The weekly reminders are fixed, and there's a regression test that fails on the old code. Nothing is committed.

**The fix** (`src/dispatch/case/scheduled.py`): the Monday check compared `isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. I replaced it with a named constant, `MONDAY_ISOWEEKDAY = 1`, with a comment saying it's ISO numbering. The `_is_reminder_day()` helper and both reminder jobs are unchanged.

**The test** (`tests/case/test_case_scheduled.py`, new file, 9 tests):
- `_is_reminder_day()` returns True only on Monday, checked for all seven days of the week.
- `case_stable_reminder` sends the close reminder for a stable case older than a week when the date is a Monday.
- The same job sends nothing on Tuesday.

The job is looked up from the scheduler's registered tasks and called with the test database session, so the test runs the real job logic, not a copy.

**Verification:**
- The new tests pass: 9 passed.
- I reintroduced the bug by setting the constant to 0. The Monday tests failed with "Called 0 times", which matches the production symptom. I then restored it to 1.
- `python -m pytest tests/case tests/case_cost` passes: 43 passed.
- `ruff check` passes, and `ruff format` was applied to the new test file.

**Left alone:** the daily `TypeError` from `case_close_reminder` on cases with no `triage_at` is still there. It doesn't cause the missing reminders, but it's the same kind of guard `32fa810f` added for `stable_at`, and it's a small follow-up if you want it. I didn't include it in this change to keep the fix focused.

----- next turn -----



----- next turn -----

The nightly TypeError is fixed. Cases with no `triage_at` now count their weeks from `created_at`, so they get the Monday reminder like everything else. Nothing is committed.

**Cause:** `case_close_reminder` runs `datetime.utcnow() - case.triage_at`. `triage_at` is only set by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`) when a case transitions into triage, and only if it isn't already set. Triage cases that never went through that path have a null `triage_at`, so the subtraction raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `except` logs it, which is why it shows up every evening. The log has 40 of these from 2025-07-28 onward. I couldn't identify which cases have the null value because I don't have database access here.

**Fix** (`src/dispatch/case/scheduled.py`): `triaged_at = case.triage_at or case.created_at`, with a comment explaining the fallback. The weekly check itself is unchanged.

**Tests** (`tests/case/test_case_scheduled.py`, two new tests for the job):
- A triage case with no `triage_at` that was created 8 days ago gets the reminder on Monday.
- A triage case with no `triage_at` created 2 days ago gets nothing.

I reverted the fix temporarily, and the first test failed with the same TypeError as production. I then restored it.

**Verification:** `python -m pytest tests/case tests/case_cost` passes, 45 tests. `ruff check` and `ruff format --check` are clean on both files.

Working tree: `M src/dispatch/case/scheduled.py` and `?? tests/case/test_case_scheduled.py`. Do you want a commit?

----- next turn -----

Four commits since 2025-05-22 changed the snooze or dedup decision or its windows. Nothing was changed in the repo.

**Windows as the code applies them today**
- **Default dedup window** (signals with no dedup filter): 45 minutes. `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, overridable by env var, and it's converted to seconds before use.
- **Custom dedup filter window** (`SignalFilter.window`): seconds, used directly as `_window_start(f.window)` (`src/dispatch/signal/service.py:846`). The API schema default is 600 (10 minutes, `models.py:282`), and the DB column default is 3600 (1 hour, `models.py:206`).
- **Snooze**: no time window. It's an absolute `expiration` datetime on the filter.

**Commits**

1. **`a348bbd2`** (2025-05-29), `fix(signal): don't dedup on canary signals`. Canary instances skip dedup entirely, and canary instances are excluded as dedup matches on both the default and custom paths. No window change.

2. **`7a9fe810`** (2025-06-19), `feat(signal): make the default deduplication window configurable`. The default window moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45. Effective window is now 45 minutes.

3. **`086dc910`** (2025-08-07), `refactor(signal): simplify snooze filter checks`. Two changes:
   - An expired snooze filter now `break`s out of the loop instead of `continue`ing. Any later snooze filter on the same signal is no longer evaluated once an expired one is hit. This is a behavior change that the commit doesn't mention.
   - The `mode`/`action` missing-value warnings were folded into one condition. Behavior there is unchanged.

4. **`917a0b7b`** (2025-08-14), `refactor(signal): share the lookback window computation`. The custom dedup window changed units. It was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as seconds. The model already documented seconds, so the code now matches the declared unit. But this is a silent 60× change for existing filters: a stored `window` of 600 used to mean 10 hours and now means 10 minutes. The commit has no body and no data migration, so I couldn't find anything that converts stored values. You'd need to check existing filter rows in production.

Two other things came up that I didn't count as changes to the decision:
- `5e136d7b` and `d2675cf4` touched the signal UI and raw-field masking, not the snooze or dedup logic.
- The `600` schema default predates the window and wasn't changed since May 22.

----- next turn -----

The 30-minute window now works as the UI says, and the regression test fails on the old code. Nothing is committed.

**Cause:** commit `917a0b7b` (2025-08-14, "share the lookback window computation") changed how a custom dedup filter's window is read. The UI labels the field "Window (minutes)" with options 5–30, and the stored values are minutes. The commit started reading them as seconds, so a 30-minute window became 30 seconds. Two instances ten minutes apart fall outside 30 seconds, so the second one opened its own case. The other commit I listed, `086dc910`, changed snooze handling and doesn't affect windows.

**Fix** (`src/dispatch/signal/service.py`): the window is now converted from minutes to seconds before the lookback is computed, with a comment stating the unit. Existing filters need no edits because their stored values are already in minutes. I also corrected the comment on `SignalFilter.window` in `src/dispatch/signal/models.py` to say minutes.

**Regression test** (`tests/signal/test_signal_service.py`, parametrized, 2 cases): a filter with window 30 deduplicates an instance from 10 minutes earlier, and doesn't deduplicate one from 40 minutes earlier. With the bug restored, the 10-minute case fails. The fix is back in place.

**Verification:** `python -m pytest tests/signal tests/case tests/case_cost` gives 79 passed, 1 skipped. `ruff check` passes on `src` and the test directories I touched.

**Not changed, for you to decide:**
- The model defaults are still 3600 for the column and 600 for the API schema. Under the minutes meaning they are 60 hours and 10 hours. That was already how they behaved before `917a0b7b`, so I left them alone.
- The repo has pre-existing formatting complaints in `tests/signal/test_signal_flow.py` and `src/dispatch/signal/models.py:416`. Those lines weren't touched by my changes.

**Working tree** (all uncommitted): the earlier `triage_at` fix in `src/dispatch/case/scheduled.py` with its new test file `tests/case/test_case_scheduled.py`, plus this window fix. Say if you want a commit.

----- next turn -----

The cause was `086dc910` (2025-08-07, "simplify snooze filter checks"). It changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. Once the loop reached an expired filter, it stopped checking the rest of the signal's filters. For "Okta: Impossible travel", the expired filter for that user was listed first, so the valid one was never evaluated and new instances were not snoozed.

**Fix** (`src/dispatch/signal/service.py`): restored `continue`, so an expired snooze is skipped and the loop goes on to the next filter.

**Regression test** (`test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`): one snooze filter for the entity expired a week ago, a second is valid for 30 days, and a new instance for that entity should be snoozed. With the `break` restored, the test fails. With `continue`, it passes.

**Verification:** `python -m pytest tests/signal tests/case tests/case_cost` gives 80 passed, 1 skipped. `ruff check` passes on `src`, and the touched test and service files are formatted.

**Still uncommitted** in the working tree, from this session:
- the `triage_at` fallback in `src/dispatch/case/scheduled.py` and its tests
- the minutes-unit window fix in `src/dispatch/signal/service.py` and `models.py`, with its test
- this snooze fix and its test

Let me know if you want these committed.

----- next turn -----

**Weekday reminders (case close and stable reminders)**

Weekly Monday reminders stopped going out. The Monday check compared `date.isoweekday()`, which numbers Monday as 1, against `calendar.MONDAY`, which is 0, so the check never passed. Commit `c509d45e` introduced it, and it reached production in image `main-81d8ae42` on 2025-08-13. The first missed Monday was 2025-08-18. I replaced the constant with `MONDAY_ISOWEEKDAY = 1` and added `tests/case/test_case_scheduled.py`. With the bug restored, the Monday test fails with "Called 0 times".

**Nightly TypeError (case close reminder)**

Every evening, `case_close_reminder` logged a `TypeError` for triage cases whose `triage_at` was null. The job subtracted `triage_at` from the current time, so those cases never got their weekly reminder. `triage_at` is only set by the triage transition flow, so cases that never went through it had no value. The job now counts from `created_at` when `triage_at` is missing. Two tests cover this, and one of them fails with the old code. I didn't identify which production cases lack `triage_at`, because I had no database access.

**Deduplication windows (signals)**

Commit `917a0b7b` made custom dedup windows read the UI's minutes value as seconds, so a 30-minute window became 30 seconds. I restored minutes, so existing filters need no edits. A regression test covers this.

**Snoozing (signals)**

Commit `086dc910` changed an expired snooze from `continue` to `break`, so an expired filter stopped the check for the signal's other snooze filters. That is why "Okta: Impossible travel" stopped snoozing for that user. I restored `continue`, and a regression test covers it.

**Canary dedup (signals)**

Commit `a348bbd2` made canary signals skip deduplication and excluded them as dedup matches. The behavior is intended, but it does change how canaries are deduplicated.

**Open items**
- Model defaults for the window (column default 3600, API default 600) are read as minutes, which makes them 60 hours and 10 hours. I left them alone.
- Some formatting complaints remain in files I didn't touch (`tests/signal/test_signal_flow.py`, `src/dispatch/signal/models.py:416`).

**Working tree status:** nothing is committed. Changes are in `src/dispatch/case/scheduled.py`, `src/dispatch/signal/models.py`, `src/dispatch/signal/service.py`, and `tests/signal/test_signal_service.py`. The new file is `tests/case/test_case_scheduled.py`.

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