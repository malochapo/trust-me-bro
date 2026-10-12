**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` in `src/dispatch/case/scheduled.py` with a shared helper:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. The helper therefore never returns true, so `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) never send anything. The jobs still run at 18:00 every day, so nothing errors or alerts. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why it still arrives.

**Deploy:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out at 2025-08-13 16:40Z. Both the scheduler and the web pod started on it at that time.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", from 2025-08-12. `c509d45e` is an ancestor of it.
- The previous image, `main-b05613b5` (deployed 2025-07-30), does not contain `c509d45e`.
- The `c509d45e` refactor was bundled into this deploy along with about 30 other commits. The image tag doesn't point at it by name.

**Log evidence:**
- Close reminders were sent on Monday 07-28 (4), 08-04 (6) and 08-11 (5), all on the old image.
- The first Monday after the deploy, 08-18, has zero "Case close reminder sent" lines. The jobs ran and finished in about 0.03 s with nothing sent.
- The Monday jobs on 08-18 hit the same error described below, but that doesn't explain the silence. The 08-11 jobs hit it too, and reminders still went out.

**Separate, older problem:** every day, including before the regression, `case_close_reminder` and `case_stable_reminder` log `TypeError: datetime - NoneType`.
- `case.triage_at` is `None` for at least one triage case. A matching `case.stable_at` error appears for stable cases in the earlier logs.
- The per-case `try/except` catches it, so the other cases still get reminders.
- Commit `32fa810f` added an `if case.stable_at` guard to the stable job. The close job has no such guard and still logs the error.
- It is unrelated to the missing reminders, but it means that case is silently skipped.

**Fix (not applied, as you asked):** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. A small test for `_is_reminder_day()` on a known Monday would catch this kind of mistake. Reminders won't resume until the fix is deployed. The next Monday after that is when they'll go out.

----- next turn -----

I fixed the Monday check and added a regression test. The new test passes with the fix. I didn't run the rest of the suite or commit anything.

- **Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, the same as `calendar.MONDAY`. The old code used `isoweekday()`, which counts Monday as 1.
- **Test:** `tests/case/test_case_scheduled.py` freezes today's date and checks `_is_reminder_day()` for each day of the week starting Monday 2025-08-18. It expects true only on Monday.
- **Check that it catches the bug:** with the fix stashed, the Monday case fails and the other six pass. With the fix, all seven pass.

The weekly reminders only come back once this is deployed. They'll go out on the first Monday after that.

I left the separate `triage_at is None` error alone. It is still logged every day by `case_close_reminder`, and that case is skipped.

----- next turn -----

Fixed. All 9 tests in `tests/case/test_case_scheduled.py` pass, including the 2 new ones, and I didn't run the rest of the suite or commit anything. With `src/` stashed, the 2 new tests fail along with the earlier Monday test.

**Cause:** the close reminder job counts how long a case has been in triage from `case.triage_at`. That timestamp is only set when a case moves into triage through the status-transition flow (`case_triage_status_flow` in `case/flows.py`). Cases created directly in Triage, or created before the column existed, have `triage_at = None`. `datetime.utcnow() - None` then raises the `TypeError` every evening. The per-case `try/except` catches it, so those cases were never reminded, even on Mondays.

**Fix:** in `src/dispatch/case/scheduled.py`, `case_close_reminder` now counts from `case.triage_at or case.created_at`. A short comment there explains why.

**Tests:**
- Cases with no `triage_at` that were created 8 days ago now get the reminder.
- A case created 2 days ago does not.
- A case with `triage_at` set still counts from it.
- A separate test checks that no ERROR is logged.

`CaseFactory` ignores the `status=` argument, because `status` is declared under its `Params` and never reaches the model. Cases always come out as "New". My tests set the status after creating each case. I left the factory alone, but that quirk could trip up other tests.

I didn't touch `case_stable_reminder`. It skips cases with no `stable_at` through an explicit guard, and you only asked about the close job. If stable cases can also lack that timestamp, the same created-at fallback would apply there. Say if you want it.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 touch the snooze/dedup decision. Three change behaviour, and two of those are labelled "refactor". Everything is in `src/dispatch/signal/service.py` unless noted. I haven't changed any code.

**Behaviour changes**

- **`a348bbd2` (2025-05-29), "don't dedup on canary signals" (#6026).**
  - `filter_dedup` now returns early when the new instance is a canary.
  - Both dedup queries (the no-filters default and the per-filter one) also exclude canary instances from the candidates, with `~SignalInstance.canary`.
  - It adds no window values. It also rewrote `tests/signal/test_signal_service.py`.

- **`7a9fe810` (2025-06-19), "make the default deduplication window configurable".**
  - The window for signals with no filters was a hard-coded `timedelta(hours=1)`. It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
  - **Today's value: 45 minutes**, from the setting's default. The code applies it as minutes, via `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`.
  - The default dropped from 60 to 45 minutes. Unless a deployment sets the env var, signals without filters now dedup over a shorter lookback than before. The commit message doesn't mention this.

- **`917a0b7b` (2025-08-14), "share the lookback window computation".**
  - It adds `_window_start(seconds)`, which returns now minus `timedelta(seconds=...)`. Both dedup paths now use it.
  - The per-filter window changed unit. It was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as seconds.
  - `SignalFilter.window` is an Integer column documented as seconds, with a default of `60*60`, and the Pydantic schema default is 600. So **today's per-filter window is `f.window` seconds**: 3600 s (1 h) by default, or 600 s (10 min) from the schema default.
  - Before this commit, the same stored 3600 was read as 3600 minutes (60 hours). Existing dedup filters now look back a much shorter time than they did, so fewer instances will dedup into existing cases. The code now matches the column's definition, but a "refactor" commit shouldn't have changed it.

- **`086dc910` (2025-08-07), "simplify snooze filter checks".**
  - It merges the mode and action guards into `if f.mode != active or f.action != snooze: continue`, and drops the "no mode" and "no action" warnings. This part is behaviour-neutral apart from the lost log lines.
  - The expired-expiration branch changed from `continue` to `break`. In `filter_snooze`, the first expired snooze filter now stops evaluation of the remaining filters. An active, unexpired snooze filter that comes after an expired one is no longer applied, so those instances can create cases instead of being snoozed.
  - Snooze has no window. It compares `f.expiration` (treated as UTC) with now, and that comparison is unchanged.

**No effect on the decision**

- `4474af25` (2025-06-10) only adds `log.info` lines in `signal/flows.py`.
- `d2675cf4` and `5e136d7b` (both 2025-07-03) don't touch snooze or dedup logic.
- `dee1699d` (2025-08-15) only touches the unrelated `snooze_extension_oncall_service_id` field.

I only searched commits that touch `src/`. Say if you want me to check tests or other paths as well.

----- next turn -----

Commit `917a0b7b` (2025-08-14, "share the lookback window computation") caused it. The fix and a regression test are in place. The signal tests pass with the fix, and the new test fails without it. I haven't run the wider suite and haven't committed.

**Cause:** the filter window is entered and stored in minutes. The UI field is labelled "Window (minutes)" with choices 5, 10, 15, 20 and 30, so "30" is saved as 30. Until that commit, the code used it as `timedelta(minutes=f.window)`. The refactor swapped in a helper that takes seconds and passed it `f.window` unchanged. The comment it added, "stored in seconds", copied the misleading comment on the model column. Your 30-minute window therefore became 30 seconds, and two instances ten minutes apart opened two cases. Filters that don't have a deduplication window of their own were unaffected, because the signal's default window path was converted correctly.

**Fix:**
- In `src/dispatch/signal/service.py`, `filter_dedup` now calls `_window_start(f.window * 60)`. Existing filters work without being edited, because their stored values were always minutes.
- In `src/dispatch/signal/models.py`, I corrected the column comment to say minutes.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. An earlier instance for the same entity is 10 minutes old. With `window=30` the new instance is deduplicated, and with `window=5` it is not.

**Things to know:**
- **Column default:** the column default is still `60*60` and the Pydantic schema default is 600. As minutes these are 60 hours and 10 hours. Neither is reachable from the UI, so I left them alone. Changing the column default would need a migration.
- **Weak existing test:** the existing `test_filter_actions_deduplicate` doesn't test the filter path. The factory call inside `signal.filters.append(...)` expires the relationship, so the append is lost and the test only exercises the no-filter default path. My test creates the filter before appending it for that reason.
- **Snooze:** the other behaviour change from my earlier list, `continue` becoming `break` for an expired snooze filter in `086dc910`, is a separate problem and is not fixed here.

----- next turn -----

This is the same batch of changes. Commit `086dc910` (2025-08-07, "simplify snooze filter checks") caused it. The fix and a regression test are in place, and nothing is committed.

**Cause:** `filter_snooze` loops over the signal's filters. Before that commit, an expired snooze filter hit `continue` and the loop moved on to the next filter. The refactor changed that to `break`, which ends the whole loop. When the expired filter comes before the valid one in the list, as in your "Okta: Impossible travel" case, the valid filter is never evaluated. The instance isn't snoozed and opens a case.

The bug depends on filter order. If the valid filter happens to come first, the loop snoozes before reaching the expired one. That is probably why only some signals reported it.

**Fix:** in `src/dispatch/signal/service.py`, the expired branch goes back to `continue`. The other `break`s in that function are correct, because they sit right after an instance is snoozed.

**Test:** `test_filter_actions_snooze_expired_filter_does_not_hide_valid_one` in `tests/signal/test_signal_service.py`. It gives one signal an expired snooze filter (7 days ago) followed by a valid one (30 days ahead), both matching the same entity. It asserts the filters load in that order and that the instance ends up snoozed.

With the `src/dispatch/signal` changes stashed, this test and the dedup-window test from earlier both fail. With them applied, all signal tests pass, 34 passed and 1 skipped. I haven't run the rest of the suite.

The same refactor also removed the "no mode" and "no action" warnings. A filter with no mode or no action is still skipped silently, so that change only costs you those log lines.

----- next turn -----

Four things were wrong. Two came from "refactor" commits that changed behaviour, one affected stored data the code reads, and one was a gap in how the job reads case timestamps. All four are fixed and have regression tests. Nothing is committed, and I only ran the signal tests and the new case-scheduler tests, not the full suite.

**1. Weekly Monday reminders stopped (long-running triage and stable cases)**
- Commit `c509d45e` (2025-08-12, "share the weekly reminder check") moved the Monday check into a new helper, `_is_reminder_day`, in `src/dispatch/case/scheduled.py`.
- The old inline check was `date.today().isoweekday() == 1`. The helper compares `isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0), so it was true on Sundays and never on Mondays. Both `case_close_reminder` and `case_stable_reminder` use the helper, so both weekly reminders stopped.
- The commit shipped to production as image `registry.example.com/dispatch:main-81d8ae42`, started at 2025-08-13 16:40Z. The first Monday after that is 2025-08-18, the first one without reminders.
- Daily triage reminders kept working because they never use that helper.
- The fix compares `date.today().weekday()` to `calendar.MONDAY`. The new test file `tests/case/test_case_scheduled.py` covers each day of the week.

**2. Evening `TypeError` in the case close reminder**
- The job counts how long a case has been in triage from `triage_at`, which is only set on status transitions. Cases created directly in triage, or before the column existed, have none.
- The subtraction raised the `TypeError`, and the per-case `try/except` logged it and skipped the case, so those cases never got a reminder.
- It now counts from `triage_at or created_at`, with tests for both paths. I left `case_stable_reminder` as it was, with its `stable_at` guard.

**3. Deduplication windows far too short**
- Commit `917a0b7b` (2025-08-14) added a seconds-based helper and passed it the filter window unchanged. The UI and the stored values are in minutes, so a window of 30 minutes became 30 seconds.
- `filter_dedup` now converts with `f.window * 60`, so existing filters work without edits. I also corrected the misleading column comment.
- The new test uses an earlier instance 10 minutes old. A 30-minute window groups it and a 5-minute window does not.

**4. Snoozing broken when an expired filter comes first**
- Commit `086dc910` (2025-08-07) changed an expired snooze filter's `continue` to `break` in `filter_snooze`, which ended the loop. A valid snooze filter listed after an expired one was never checked.
- It is back to `continue`. The new test puts an expired filter before a valid one and expects the instance to be snoozed.

**Canary signals and the default window**
- Commit `a348bbd2` (2025-05-29) stops canary signals from being deduplicated and keeps canary instances out of the candidates.
- Commit `7a9fe810` (2025-06-19) made the default window for signals without filters configurable. It dropped the default from 1 hour to 45 minutes without saying so in the commit message.

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