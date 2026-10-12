**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday check into a helper that compares the wrong weekday numbering:

```python
# src/dispatch/case/scheduled.py
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's calendar module starts the week on Monday = 0). I confirmed both values in the interpreter. The helper is therefore False every day of the week. The old inline check was `date.today().isoweekday() == 1`, which was correct.

The helper is used by both weekly reminders:
- `case_close_reminder` (long-running triage cases, around line 49)
- `case_stable_reminder` (long-running stable cases, around line 95)

The daily `case_triage_reminder` does not call the helper, which is why those reminders still arrive.

**Evidence from the logs:**
- Case close reminders were sent on Mondays before the deploy: 5 on 07-28, 7 on 08-04, and 6 on 08-11.
- On Monday 08-18 the scheduler logged no case close reminders. It still logged the incident close reminder, which uses a separate code path.
- Daily case triage reminders continued throughout.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. The kubelet logs show both the web and scheduler pods started on it at 2025-08-13 ~16:40 UTC, replacing `main-b05613b5`, which was running from 07-30. Commit `81d8ae42` is `fix(case): exclude resolved_by in update (#6183)`, and `c509d45e` is an ancestor of it and falls in the range `b05613b5..81d8ae42`. The same deploy also included `32fa810f` ("fix(scheduler): not all cases have a stable_at date"), which fixed the `NoneType` errors in `case_stable_reminder` that had been logged every day since 07-28. That fix was correct, but it is not the cause of the missing reminders.

**Suggested fix (not applied, per your request):** change the helper to use `date.today().weekday() == calendar.MONDAY` (0-based, matching `calendar.MONDAY`), or to compare `isoweekday()` with 1. A test that pins the helper to a known Monday would catch this regression.

I made no code changes.

----- next turn -----

The fix is in and the regression tests pass. The new tests fail on the old code, and the full `tests/case` suite passes (25 tests) with `python -m pytest`.

**The fix** (`src/dispatch/case/scheduled.py`):

```python
return date.today().weekday() == calendar.MONDAY
```

`weekday()` is 0-based like `calendar.MONDAY`, so Monday matches. The previous `isoweekday()` is 1-based, which is why the check never matched.

**The regression test** (`tests/case/test_case_scheduled.py`, new file):
- `test_is_reminder_day` checks every weekday with the date pinned, so Monday must be True and Tuesday through Sunday False.
- `test_case_stable_reminder_sends_on_monday` and `test_case_close_reminder_sends_on_monday` run the real reminder functions on a Monday and assert that the reminder is sent for a case stable or triaging for more than a week.
- `test_case_stable_reminder_skips_other_days` checks that nothing is sent on a Tuesday.

The tests call the original undecorated functions, found through `scheduler.registered_tasks`, so they skip the project-context and timing decorators. Reverting the one line to `isoweekday()` makes the three Monday-dependent tests fail with "Called 0 times". I restored the fix afterwards.

**Notes:**
- The test file changed on disk while I was working on it. I kept the current version, which is the one I ran. It uses the registry lookup, the same approach I was taking.
- I did not commit anything.

----- next turn -----

The close-reminder TypeError is fixed. Cases in triage with no `triage_at` now count from `created_at`, and they get their weekly reminder. The `tests/case` suite passes (27 tests, run with `python -m pytest`).

**Cause:** `case_close_reminder` runs `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at = NULL`, and subtracting `None` raises the TypeError. The error is caught per case, so one bad case causes one logged error each evening, and that case never gets a reminder. `triage_at` is only set by `case_triage_status_flow` (`src/dispatch/case/flows.py`). Some paths put a case into triage without running that flow, including the Slack handlers at `plugins/dispatch_slack/case/interactive.py` around lines 1427 and 2246, which assign `case.status = CaseStatus.triage` directly. I didn't confirm which path created the affected cases, since the log lines don't include case IDs.

**Fix** (`src/dispatch/case/scheduled.py`):

```python
span = datetime.utcnow() - (case.triage_at or case.created_at)
```

**Tests** (added to `tests/case/test_case_scheduled.py`):
- `test_case_close_reminder_counts_from_created_at_when_triage_at_missing`: a Monday case with no `triage_at` and created 8 days ago gets the reminder. It fails on the old line with the same TypeError.
- `test_case_close_reminder_prefers_triage_at_over_created_at`: when `triage_at` is set, it still takes precedence, so a case triaged 2 days ago gets no reminder even if created 30 days ago.

**Things to know:**
- `created_at` is timezone-aware when Python creates the row, but the column is a naive `DateTime`. Cases loaded from the database are naive, so the subtraction works. I didn't normalize it.
- The stable-reminder job has the same kind of gap, but it skips cases with no `stable_at` rather than counting from another date, so those cases never get a reminder. I didn't change that since you asked only about the close-reminder job. Tell me if you want the same fallback there.
- The uncommitted diff also still contains the earlier Monday fix (`weekday()`), and nothing is committed.

----- next turn -----



----- next turn -----

Since 2025-05-22, four commits changed the snooze or dedup logic or its windows. None of them changed the code I read earlier in `scheduled.py`. I didn't change any code.

**Current windows, as the code applies them**

- **Default dedup window:** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes** (`src/dispatch/config.py:95-97`). `filter_dedup` multiplies it by 60 and subtracts it as seconds (`signal/service.py:805`, helper at `:784-786`).
- **Per-filter dedup window:** `SignalFilter.window` is an Integer in **seconds** (`signal/models.py:206-208`, column default 3600, i.e. 1 hour). The pydantic default is 600 (`signal/models.py:282`). `filter_dedup` subtracts it as seconds (`service.py:845-846`).
- **Filter UI:** the create dialog labels the field "Window (minutes)", offers 5, 10, 15, 20, and 30, and sends the number unchanged (`static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:57-58, 196`).
- **Snooze:** I found no time window for snooze itself. A snooze lasts until `filter.expiration`. I didn't check whether the snooze query has its own time bound.

**Commits since 2025-05-22**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals (#6026)". Canary instances skip `filter_dedup` and are excluded from the dedup match query (`service.py`, `~SignalInstance.canary`).

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable". The default dedup window was a hardcoded 1 hour (`timedelta(hours=1)`). It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes**. This shortened the default window by 15 minutes unless the environment overrides it.

3. **`086dc910`** (2025-08-07), "refactor(signal): simplify snooze filter checks". Two changes in `filter_snooze`:
   - The mode and action checks were merged into one condition. The "has no mode" and "has no action" warnings were removed. Filters with those fields missing are still skipped, but silently now.
   - When a snooze filter's expiration has passed, the loop changed from `continue` to **`break`**. Later snooze filters in the list are no longer evaluated after the first expired one. This is a behavior change, not a refactor.

4. **`917a0b7b`** (2025-08-14), "refactor(signal): share the lookback window computation". This is the one most likely to matter. The per-filter window was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as **seconds**. The commit adds the comment "SignalFilter.window is stored in seconds", but the code path changed without any change to the stored data. Effect:
   - A filter with the model default of 3600 went from a 3600-minute window to 3600 seconds (60 hours to 1 hour).
   - A filter the UI created with "30" went from 30 minutes to **30 seconds**, even though the UI still says "minutes".

   The commit's diff does not say whether this was intended, so it may be an accidental unit change.

I also checked `4474af25` (outcome logging). Its diff doesn't touch `signal/service.py`, so I'm not counting it as a change to the snooze or dedup decisions. I didn't read its full diff.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the per-filter dedup window from `timedelta(minutes=f.window)` to a seconds-based helper. A window of 30 now looks back 30 seconds, so the two instances ten minutes apart never group. The UI labels the field "Window (minutes)", so the code was out of step with it.

**Fix** (`src/dispatch/signal/service.py`):
- `_window_start` now takes minutes and returns `now - timedelta(minutes=...)`.
- The per-filter window passes `f.window` directly, so it means minutes again. Existing filters keep their stored values and behave as they did before 2025-08-14. No data changes are needed.
- The default dedup window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`. Its behavior is unchanged.

**Tests** (`tests/signal/test_signal_service.py`): `test_filter_window_is_in_minutes` is parametrized over two cases:
- An instance 10 minutes earlier with a window of 30 is deduplicated.
- An instance 40 minutes earlier with a window of 30 is not.

The 10-minute case fails on the regressed line and passes with the fix.

**Results:**
- `python -m pytest tests/signal tests/case`: 61 passed, 1 skipped.
- Full suite, excluding `tests/ai`: 363 passed, 4 skipped, 2 failed. Both failures (`test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`) also fail with my changes stashed.
- `tests/ai` fails because it downloads a tokenizer and there is no network access. It fails the same way without my changes.

**Not changed, needs your decision:**
- The model defaults still assume seconds: `SignalFilter.window` has a column default of 3600 (`signal/models.py:206-208`) and the pydantic default is 600 (`:282`). Under minutes they would mean 60 hours and 10 hours. The UI always sends a value, so this only matters for filters created without one. I left the defaults alone because changing them alters what new filters get.
- If any filter was created through the API with a seconds value, it now behaves as a minutes value. I can't tell from the code which filters exist.
- The `break` change in `086dc910` is still in place. After an expired snooze filter, later snooze filters are skipped. It's a separate behavior change, so I left it alone.

Nothing is committed.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, "simplify snooze filter checks"). In `filter_snooze`, it changed the expired-snooze branch from `continue` to `break`. The first expired filter in the list therefore ended the loop, and the active filter after it was never checked. The new instances were not snoozed.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): the expired branch is back to `continue`, so the loop moves on to the next snooze filter. The rest of that function is unchanged.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_expired_then_active` puts an expired snooze filter before a valid one that matches the instance's entity, then expects the instance to be snoozed. With `break` restored, the test fails. With `continue`, it passes.

**Results:** `python -m pytest tests/signal tests/case` gives 62 passed, 1 skipped.

The file changed on disk after my edit. I checked the current diff, and the `continue` fix is still there, along with the earlier minutes fix. The test run used that current state.

Nothing is committed. The remaining known gaps are the ones from the previous report: the model defaults still assume seconds, and `tests/ai` needs network access.

----- next turn -----

**Recap for the weekly report**

**Investigation 1: missing Monday reminders.** Assignees stopped getting the weekly Monday close reminders for long-running triage and stable cases. The daily triage reminders kept arriving. The cause was commit `c509d45e` (2025-08-12, "share the weekly reminder check"). It changed `_is_reminder_day()` to compare `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check was always false. The fix uses `weekday()`, and tests cover all seven weekdays and both reminder jobs. The bad commit reached production in image `main-81d8ae42`, deployed 2025-08-13 16:40 UTC. The previous image, `main-b05613b5`, predates the commit. The first Monday that was missed is 2025-08-18.

**Investigation 2: the close reminder TypeError.** The `case-close-reminder` job logged a TypeError every evening. The job ran `datetime.utcnow() - case.triage_at`, and some triage cases have `triage_at` set to NULL. Only `case_triage_status_flow` sets that field, and some paths put a case into triage without running it. The fix counts from `created_at` when `triage_at` is missing. Two tests cover the fallback and the precedence of `triage_at`. I did not confirm which code path created the affected cases.

**Investigation 3: the window and snooze reports.**
- **Deduplication windows.** Commit `917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds. A filter set to 30 in the UI looked back 30 seconds, so instances ten minutes apart were not grouped. The fix restores minutes. Existing filters keep their stored values and behave as they did before the change, and a regression test covers the 10- and 40-minute cases.
- **Snoozing.** Commit `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired filter earlier in the list ended the loop, so a valid filter after it was never checked. The fix restores `continue`, with a regression test.
- **Canary signals.** Commit `a348bbd2` (2025-05-29) made canary signals skip deduplication and excluded them from the dedup query.
- **Default grouping window.** Signals with no filters use a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Commit `7a9fe810` (2025-06-19) made this configurable and shortened the default from one hour to 45 minutes.

**Test results:** `python -m pytest tests/signal tests/case` gives 62 passed and 1 skipped. The rest of the suite, excluding `tests/ai`, gives 363 passed, 4 skipped, and 2 failures. Both failures also occur with my changes stashed. `tests/ai` needs network access to download a tokenizer and fails with or without my changes.

**Open items, not changed:**
- The default filter values still assume seconds (`SignalFilter.window` defaults to 3600 and the API default is 600), which would now be read as minutes.
- A filter created through the API with a seconds value would now behave as minutes.
- Case-stable reminders skip cases with no `stable_at` instead of falling back to another date.

Nothing is committed.

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