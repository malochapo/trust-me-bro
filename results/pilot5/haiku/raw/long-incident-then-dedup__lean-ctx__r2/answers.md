**Root cause:** the Monday check added in `c509d45e` compares against `calendar.MONDAY`, which is `0` in Python's `calendar` module. `date.today().isoweekday()` returns `1` for Monday. The condition is never true, so the weekly close and stable reminders are never sent. The daily triage reminder doesn't go through this check, which is why it still arrives.

**The code** (`src/dispatch/case/scheduled.py:31-33`):

```python
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

It's used at lines 49 (`case_close_reminder`) and 95 (`case_stable_reminder`). Before the refactor, the same logic was inline as `date.today().isoweekday() == 1`, which was correct. The refactor changed the literal `1` to `calendar.MONDAY` and broke it. I didn't run the Python check because inline `python3 -c` is blocked here, but `calendar.MONDAY == 0` is documented stdlib behaviour.

**The deploy that shipped it:**
- `c509d45e` ("refactor(case): share the weekly reminder check"), authored 2025-08-12, is an ancestor of `81d8ae42`.
- The scheduler and web pods restarted on **2025-08-13 at 16:40Z** running `registry.example.com/dispatch:main-81d8ae42`. That is the first deploy containing the bug.

**Log evidence:**
- Monday 2025-08-11 (old image `main-b05613b5`, deployed 07-30, before the refactor): six "Case close reminder sent" lines at 18:00.
- Monday 2025-08-18 (new image): the case-close and case-stable jobs ran at 18:00 and sent nothing. Only the daily "Case triage reminder" and "Incident close reminder" lines appear.
- The API log has no reminder entries, so the fault is in the scheduler.

**Side finding, not the cause:** `case_close_reminder` logs a `NoneType` subtraction error on every daily run (`scheduled.py:47`, `case.triage_at` is `None` for some cases). The per-case `try/except` catches it, so it doesn't block other cases. Commit `32fa810f` added the `if case.stable_at:` guard to the stable reminder, but the close reminder has no equivalent guard. Fixing this is worth doing alongside the Monday fix, because the same loop runs the weekly send.

I haven't changed any code. The fix would be to change `calendar.MONDAY` back to `1` (or use `datetime.weekday() == 0`, which is Monday in that API), plus the `triage_at` guard. Do you want me to make that change?

----- next turn -----

The Monday fix is in, and a regression test covers it. The new tests pass against the local PostgreSQL, and the test fails when the bug is put back. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py`):
- `_is_reminder_day()` now compares `isoweekday()` to `1`, the ISO value for Monday. I removed the `calendar` import, which is no longer used.
- `case_close_reminder` now skips cases with no `triage_at`, mirroring the existing `stable_at` guard in the stable reminder. Before, every daily run logged a `NoneType` error for such cases. The per-case `try/except` already kept other cases from being blocked, so this change only removes the log noise.

**The regression test** (`tests/case/test_case_scheduled.py`, new):
- `test_case_close_reminder_sends_only_on_mondays` and `test_case_stable_reminder_sends_only_on_mondays` patch `date.today()` to a Monday and a Tuesday. Each case is 8 days past its threshold. They assert that the reminder is sent on Monday and not on Tuesday.
- `test_case_close_reminder_skips_cases_without_triage_at` covers the guard.
- The tests call the registered job functions through the scheduler's `registered_tasks`. The `@scheduler.add` decorator returns `None`, so the module attribute can't be used.

**Verification:**
- `python -m pytest tests/case/test_case_scheduled.py`: 5 passed.
- With the bug reintroduced (`== 0`), the two Monday tests failed with `assert 0 == 1`. I restored the fix afterward.
- `python -m pytest tests/case tests/case_cost tests/notification`: 44 passed.
- `python -m ruff check` on the two changed files: passed. (The bare `ruff` command isn't installed here.)

The changes are uncommitted in the working tree. I can commit them if you want, or open a PR.

----- next turn -----

The evening `TypeError` is fixed. Cases with no `triage_at` now count their weekly reminder from `created_at`, and there's a test for it. All 21 tests in `tests/case` pass, and ruff is clean.

**What causes it:** `case_close_reminder` subtracts `case.triage_at` from the current time. That column is NULL for some cases, and `datetime - None` raises the `TypeError`. The scheduler log has 80 of these errors between 2025-07-28 and 2025-08-20. The per-case `try/except` catches them, so the other cases still get their reminders, but the affected case never does.

`triage_at` is only written inside `case_triage_status_flow`, and most transitions into Triage go through it. The exception is the **reopen button** (`reopen_button_click`, `plugins/dispatch_slack/case/interactive.py:1427`). It sets `case.status = CaseStatus.triage` directly, so a case that is reopened without ever having recorded a triage time is left with NULL. I confirmed that the code path exists, but I haven't checked the production database to see which cases are affected. A second possibility is cases that were in Triage before the 2022-08-01 migration added the column with no backfill. I haven't verified that either.

**The fix** (`src/dispatch/case/scheduled.py`):
- The job now counts from `case.triage_at or case.created_at`. This replaces the `if case.triage_at:` guard I added last turn, so those cases are no longer skipped.
- The stable reminder still skips cases without `stable_at`. You only asked about the close reminder, so I left it alone.

**The test** (`tests/case/test_case_scheduled.py`): I replaced last turn's "skips when triage_at is missing" test with `test_case_close_reminder_counts_from_created_at_without_triage_at`. On a Monday, a case created 8 days ago gets one reminder, and a case created 3 days ago gets none. The second case shows that the job counts from `created_at` and not from now.

**Not changed:** the reopen button still writes Triage without a timestamp. Fixing that would mean routing it through `case_triage_status_flow` or setting `triage_at` there. That's a behaviour change to the UI path, so I've left it for you to decide. The changes are uncommitted in the working tree.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All of them are in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`, `_window_start`) and `src/dispatch/config.py`. I made no code changes.

**Windows as the code applies them today:**
- **Snooze:** no lookback window. A snooze filter applies until its `expiration` (a DateTime, compared to the current UTC time).
- **Default dedup** (signals with no filters): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes**, multiplied by 60 and used as **seconds**. Unless the env var is set, that is 2700 s.
- **Per-filter dedup** (`SignalFilter.window`): **seconds**. The column default is 3600 (1 hour), but the Pydantic model default is 600 (10 minutes).

**Commits:**
1. **`a348bbd2`** (2025-05-29, fix: don't dedup on canary signals): canary instances are skipped in `filter_dedup` and are excluded from the matching query on both the default and filter paths. No window change.
2. **`7a9fe810`** (2025-06-19, make the default deduplication window configurable): the default dedup window was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45, so the effective default dropped from 60 minutes to 45.
3. **`086dc910`** (2025-08-07, simplify snooze filter checks): in `filter_snooze`, an expired snooze filter used to `continue`, and now it `break`s. Once one snooze filter has expired, the later ones on that signal are no longer checked. The commit also removed the warnings for filters with no mode or action; those filters are still skipped.
4. **`917a0b7b`** (2025-08-14, share the lookback window computation): `filter_dedup` previously computed the per-filter window as `timedelta(minutes=f.window)`. It now uses `_window_start(f.window)`, which treats the value as **seconds**, matching the model comment. Existing filters have the same stored numbers, so their effective window is now 60 times shorter. For example, 3600 used to mean 60 hours and now means 1 hour.

I didn't check production filter data, and I didn't check how the UI displays the window unit. Commit `90f73fe2` changed only the snooze statistics, not the decision, so I left it out.

----- next turn -----

The cause is commit `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the filter path to read `SignalFilter.window` as seconds. Before that commit the code multiplied by 60, so a window of 30 meant 30 minutes. After it, 30 means 30 seconds, and two instances ten minutes apart never match. The UI labels the field "Window (minutes)" and saves the value unchanged, so existing filters store minutes. The other commits don't affect this: `7a9fe810` only changed the default-window path, and `086dc910` only changed snooze expiry.

**Fix** (`src/dispatch/signal/service.py`, `filter_dedup`): the window is now `_window_start(f.window * 60)`, so a stored `30` means 30 minutes again. No stored filters need editing. I also changed the comment on `window` in `src/dispatch/signal/models.py` from "seconds" to "minutes".

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_deduplicate_window_is_in_minutes`, parametrized with a window of 30:
- The first instance is 10 minutes old, so the second instance should be deduplicated. Before the fix this assertion failed.
- The first instance is 40 minutes old, so it should not be deduplicated.

`python -m pytest tests/signal` gives 34 passed and 1 skipped. Ruff check passes on the changed code. Ruff format flags `models.py:416`, but that is at the end of the file and already present at HEAD.

**Decision for you:** the `window` column default is `60 * 60`, and the Pydantic default is `600`. Both are now read as minutes, so a filter created without a window value would get 3600 minutes (60 hours) or 600 minutes (10 hours). Before this change they were 1 hour and 10 minutes. I left both alone because changing them would change behaviour for new filters. I can set them to 60 and 10 if you want them to match the old effective values.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, "simplify snooze filter checks"). In `filter_snooze`, it changed the expired-filter branch from `continue` to `break`. When an expired snooze filter came first in the signal's filter list, the loop stopped there. The valid filter after it was never checked, so new instances for that user were not snoozed.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): the expired branch uses `continue` again, so the loop moves on to the next filter.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_expired_filter_does_not_hide_valid_one`. It sets up an expired snooze filter (7 days ago) followed by a valid one (30 days ahead), both matching the same entity. The instance should be snoozed. The test failed before the fix and passes after it.

`python -m pytest tests/signal` gives 35 passed and 1 skipped. Ruff check and format pass on the changed files.

This bug is separate from the window-unit change in `917a0b7b` that I fixed earlier. The changes are uncommitted.

----- next turn -----

**Weekly Monday reminders (close and stable cases)**
The reminder check compared `calendar.MONDAY`, which is 0, with `date.isoweekday()`, which is 1 for Monday, so it never matched. Commit `c509d45e` (2025-08-12) introduced that comparison. It shipped in image `main-81d8ae42`, deployed 2025-08-13. The last Monday with reminders was 2025-08-11 (6 sent). I fixed `_is_reminder_day()` to compare against 1, and added `tests/case/test_case_scheduled.py`, which fails if the comparison is reverted.

**Nightly TypeError from the close reminder job**
`case_close_reminder` subtracted `case.triage_at` from the current time without checking for NULL. The scheduler log has 80 of these errors from 2025-07-28 to 2025-08-20. The job now counts from `triage_at`, falling back to `created_at` when it is missing. The test covers both a case created 8 days ago (one reminder) and one created 3 days ago (none). I confirmed that `reopen_button_click` can set Triage without writing `triage_at`, but I haven't checked production data to see how many cases are affected. I haven't changed the reopen path.

**Deduplication window**
Commit `917a0b7b` (2025-08-14) read `SignalFilter.window` as seconds, although the UI labels it in minutes. A filter window of 30 became 30 seconds. The fix multiplies by 60, and `test_filter_actions_deduplicate_window_is_in_minutes` covers it.

**Snoozing**
Commit `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired filter earlier in the list stopped the check, so a valid snooze filter after it was never applied. The fix restores `continue`, and `test_filter_actions_snooze_expired_filter_does_not_hide_valid_one` covers it.

**Canary signals**
Commit `a348bbd2` (2025-05-29) excluded canary instances from deduplication.

**Open items**
- The `window` column default (`60 * 60`) and the Pydantic default (`600`) are now read as minutes. New filters created without a window would get 3600 or 600 minutes. I left them unchanged and need a decision.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` was introduced in `7a9fe810` (2025-06-19), which also changed the default from 60 to 45 minutes.
- Nothing is committed yet. The changes are in the working tree.

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