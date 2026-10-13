**Root cause:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`, which compares `date.today().isoweekday()` against `calendar.MONDAY`. Those use different numbering. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Monday is 0 in `calendar`, and 1 in ISO). So the check can never be true, and the weekly reminders are silently skipped on every day, Monday included. The old code compared against the literal `1`, which was correct.

**The deploy:** `c509d45e` is in `81d8ae42`, the image `registry.example.com/dispatch:main-81d8ae42`. Both the scheduler and the API started on that image at 2025-08-13 16:40Z, replacing `main-b05613b5` from 2025-07-30.

**Evidence from the logs:**
- Monday 2025-08-11 (old image, before the refactor): 5 "Case close reminder sent" entries.
- Monday 2025-08-18 (new image): 0 close reminders sent. The stable and close reminder jobs ran with no sends.
- Daily triage reminders kept going because `case_triage_reminder` never calls `_is_reminder_day()`. That explains why only the weekly reminders stopped.
- The refactor also touched `case_close_reminder`, the triage path, so the triage weekly reminder is affected too, not just the stable one.

**Separate issues I noticed (not the cause):**
- Before 2025-08-11, `case_stable_reminder` failed every day with `NoneType` on `case.stable_at`. Commit `32fa810f` (2025-08-11) added the `if case.stable_at:` guard. That fixed the stable path, but it's why stable reminders were hidden behind the refactor bug after that.
- `case_close_reminder` still raises the same `NoneType` error on `case.triage_at` at line 47, before the Monday check. The per-case try/except doesn't cover that line, so it logs an error on every run for those cases. It doesn't stop other cases, but it's a bug.

**Fix I'd recommend (not applied, per your instruction):** in `src/dispatch/case/scheduled.py`, make `_is_reminder_day()` compare with the right value, e.g. `date.today().weekday() == calendar.MONDAY` or `date.today().isoweekday() == 1`. Also consider moving the `triage_at` / `stable_at` `None` check ahead of the division in `case_close_reminder`. I didn't check whether the tests cover `_is_reminder_day`, so I can't say whether this would have been caught.

----- next turn -----

The reminder bug is fixed and a regression test covers it. I did not commit anything.

**Fix:** in `src/dispatch/case/scheduled.py:33`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches again. The previous `isoweekday()` version compared a 1-based value against `calendar.MONDAY`, which is 0.

**Regression test:** `tests/case/test_case_scheduled.py` patches `dispatch.case.scheduled.date` and checks each day of one week. Only Monday should return True. Against the pre-fix source, the Monday case fails. With the fix, all 7 cases pass.

**Full suite:** `python -m pytest` gives 366 passed, 4 skipped, and 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those same 8 on the base commit with my changes stashed, and they fail there too, so they predate this fix. I did not investigate them.

**Not changed:** `case_close_reminder` still raises a `NoneType` error on `case.triage_at` at line 47, before the Monday check. The per-case try/except catches it, so other cases still get reminders, but the error is logged on every run. I left it alone because it's a separate bug and you asked for the reminder fix only. It's a small change if you want it in the same commit.

----- next turn -----

The close reminder job now falls back to the case's creation time when `triage_at` is missing, so those cases get their weekly reminder. The same 8 pre-existing failures remain, and I did not commit.

**Cause of the TypeError:** `case.triage_at` is `None` for some triage cases. `triage_at` is only set by `case_triage_status_flow` in `src/dispatch/case/flows.py`. Some Slack handlers set `case.status = CaseStatus.triage` directly and skip that flow, for example `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`. Those cases have no `triage_at`, so `datetime.utcnow() - None` raises the TypeError on every run. The per-case try/except catches it, so other cases still get reminders. The logs show the error at 40 entries across 2025-07-28 to 2025-08-20.

**Changes:**
- `src/dispatch/case/scheduled.py`, `case_close_reminder`: the job now counts from `case.triage_at or case.created_at`. The `created_at` fallback is naive UTC, the same as `triage_at`, because the column is stored without a timezone.
- `tests/case/test_case_scheduled.py` gets three new tests:
  - a triage case with no `triage_at` that was created 8 days ago is reminded on a Monday;
  - a triage case with no `triage_at` created 2 days ago is not reminded;
  - a case with a recent `triage_at` is not reminded even if it was created long ago.

  They call the registered `case-close-reminder` job body against a single project, not the loop over all organizations.

**Verification:** the new tests pass with the fix. With the source reverted, the created-at test fails. Full `python -m pytest`: 369 passed, 4 skipped, 8 failed. Those 8 are the same AI, database, and entity failures as before, and they also fail on the base commit.

**Not changed:** the Slack handlers still skip the triage flow. Changing them would also change what else the flow does, so I left them. The fallback covers those cases, but `triage_at` stays empty for them.

----- next turn -----



----- next turn -----

Since 2025-05-22, six commits changed the snooze or dedup logic in `src/dispatch/signal/service.py`. Nothing was changed in the code.

| Commit | Date | What it changed |
|---|---|---|
| `a348bbd2` | 2025-05-29 | Canary signals are no longer deduplicated. `filter_dedup` returns early for canary instances, and canary instances are excluded from both the default and the filter-based dedup queries. No window change. |
| `7a9fe810` | 2025-06-19 | The default dedup window (applied to signals with no dedup filter) was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, default 45. |
| `086dc910` | 2025-08-07 | Refactored `filter_snooze`. An expired snooze filter now hits `break` instead of `continue`, so the loop stops and later snooze filters on that signal are no longer checked. The "no mode" and "no action" warnings were also removed, and those filters are now skipped silently. |
| `917a0b7b` | 2025-08-14 | Added `_window_start(seconds)` and used it for both windows. The custom dedup filter window was previously `timedelta(minutes=f.window)`; it is now read as seconds. |

**Windows as the code applies them today:**
- **Default dedup (no dedup filter):** 45 minutes (2700 s). It is set by the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` env var, converted with `* 60` before use.
- **Custom dedup filter:** `SignalFilter.window` in seconds. The model's column default is 3600 s (1 hour), and the Pydantic schema default is 600 s (10 minutes).
- **Snooze:** no time window. A snooze applies until `SignalFilter.expiration`, and an expired filter stops evaluation as described above.

**Watch-outs:**
- The `917a0b7b` change makes custom dedup windows 60 times shorter for existing filters. Before it, the stored value was read as minutes; now it is read as seconds, which matches the model comment from `ecbad47f` (2022). I did not find a data migration in the history, so any existing filter with a window stored as minutes now dedups over a much shorter period.
- The `086dc910` `break` means one expired snooze filter now stops checks on later snooze filters for that signal. The commit message does not describe this as intended.
- The docstring above `filter_dedup` (around `service.py:873`) still says "1-hour window". It is out of date.

I searched commit messages and string matches for snooze, dedup, window, and lookback. A change to the snooze or dedup logic that avoids those words could be missing from this list.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). The window is now fixed, existing filters need no edits, and the full suite has the same 8 pre-existing failures as before.

**Cause:** The UI labels the field "Window (minutes)" and offers 5 to 30. Before `917a0b7b`, the code read the stored value as minutes (`timedelta(minutes=f.window)`). That commit switched it to seconds, so a 30 became 30 seconds. Two instances ten minutes apart fall outside 30 seconds, so they are not grouped. The model comment from 2022 said seconds, which is why the change looked intentional.

**Fix:**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. Both the filter window and the default dedup window use it. The default window now passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, without the `* 60`.
- `src/dispatch/signal/models.py`: the column default goes from 3600 to 60 and the schema default from 600 to 10. Those keep the same meanings (1 hour and 10 minutes) under the minutes unit. Only rows created without a value are affected, and existing rows are untouched.

**Test:** `tests/signal/test_signal_dedup_window.py` has two tests.
- A window of 30 groups an instance that is 10 minutes old. The test fails without the fix.
- An instance 40 minutes old is outside the 30-minute window and is not grouped.

**Results:** `python -m pytest`: 371 passed, 4 skipped, 8 failed. The 8 failures are the same AI, database, and entity tests that failed before my changes. Nothing is committed.

**Not changed:**
- `086dc910` still makes an expired snooze filter `break` out of the loop, which skips any later snooze filters on the signal. That is a separate issue from this bug and I didn't touch it.
- The docstring for `filter_signal` still says "1-hour window" for the default. The default is now 45 minutes.
- I did not check production data. The fix assumes stored windows are minutes, as the UI label and the code before `917a0b7b` indicate.

----- next turn -----

The cause was the `break` that commit `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks") put in `filter_snooze`. When a snooze filter has expired, the loop now stops, so any later snooze filter on the signal is never checked. In the "Okta: Impossible travel" case, the expired filter came first, so the valid one never ran and the instance was not snoozed.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): the expired branch now uses `continue`, so the loop moves on to the next filter. This is the only change to this file for this bug.

**Regression test** (`tests/signal/test_signal_snooze.py`): it has an expired snooze filter first, then a valid one for the same entity, and asserts that a new instance for that entity is snoozed. With the `break` restored, the test fails. With the fix, it passes.

I also found that `filter_snooze` raises `BadSpec` for an `EntityType` expression. That is because it has no join for `EntityType`. My first draft of the test used that shape, so I switched it to the `Entity` shape the UI produces. I did not change that behaviour, and I have not checked whether any real snooze filter uses an `EntityType` expression.

**Results:** `python -m pytest`: 372 passed, 4 skipped, 8 failed. The 8 failures are the same AI, database, and entity tests that failed before my changes. Nothing is committed.

----- next turn -----

Recap of today's work. Nothing is committed.

**1. Weekly close and stable reminders (Mondays)**
Reminders stopped after the 2025-08-13 deploy. `_is_reminder_day()` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so it never matched. Commit `c509d45e` introduced the comparison. It was deployed as `main-81d8ae42` on 2025-08-13 at 16:40Z. The first Monday with no reminders was 2025-08-18. The fix uses `date.today().weekday()`, and `tests/case/test_case_scheduled.py` covers each weekday. The test fails on the old code.

**2. Evening TypeError in the case close reminder job**
Some triage cases never set `triage_at`. Only `case_triage_status_flow` sets it, and some Slack handlers set `CaseStatus.triage` directly, skipping that flow. `datetime.utcnow() - None` then raised a TypeError on every run. The job now counts from `triage_at or created_at`, so those cases still get their weekly reminder. Three tests cover it.

**3. "GuardDuty: Unauthorized API call" dedup windows**
Commit `917a0b7b` (2025-08-14) changed the custom dedup window from minutes to seconds. A 30-minute window became 30 seconds, so two instances ten minutes apart opened two cases. The window is minutes again. The defaults in the model and schema keep their meanings (1 hour and 10 minutes). Existing filters need no edits. `tests/signal/test_signal_dedup_window.py` covers this.

**4. "Okta: Impossible travel" snoozes**
Commit `086dc910` (2025-08-07) changed an expired snooze filter from `continue` to `break`. The loop stopped at the expired filter, so a later valid snooze filter was never checked. The expired branch now uses `continue`. `tests/signal/test_signal_snooze.py` covers this.

**Results:** `python -m pytest`: 372 passed, 4 skipped, 8 failed. The 8 failures are AI, database, and entity tests that also fail on the base commit. I have not looked into them.

**Open items:**
- `case_stable_reminder` still skips cases with no `stable_at` and has no fallback. You did not ask for one.
- The Slack handlers that set triage directly still skip the transition flow.
- The docstring for `filter_signal` still says the default window is 1 hour.
- `086dc910` also removed the warnings for filters with no mode or action. Those are now skipped silently.

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