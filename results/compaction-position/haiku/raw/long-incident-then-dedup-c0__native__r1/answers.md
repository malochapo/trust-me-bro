**Root cause:** `_is_reminder_day()` compares the ISO weekday against `calendar.MONDAY`, but those use different numbering. `isoweekday()` returns 1 for Monday, while `calendar.MONDAY` is 0. The check is never true, so the weekly close reminders for triage and stable cases never send. The daily triage reminders don't use this check, so they still go out.

**Where it was introduced:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It moved the inline check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`. The original code was `date.today().isoweekday() == 1`, which was correct. The refactor replaced the literal `1` with `calendar.MONDAY`, which is 0. I confirmed this with `python3`: `calendar.MONDAY == 0`, and `date(2025, 8, 11).isoweekday() == 1`.

**Deploy that shipped it:** `81d8ae42` ("fix(case): exclude resolved_by in update", #6183), deployed as `registry.example.com/dispatch:main-81d8ae42`. The logs show the scheduler container starting on that image at `2025-08-13T16:40:06Z` (`scheduler.log:18851`), and the web container at `16:40:07Z` (`api.log:13201`). `c509d45e` is an ancestor of that commit. The previous image was `main-b05613b5`, started 2025-07-30.

**Log evidence:**
- Monday 2025-08-04 and Monday 2025-08-11 both sent case close reminders, on the old image.
- Monday 2025-08-18, on the new image, has only the incident close reminder. There are no case close reminders.
- Daily triage reminders continue through 2025-08-20.

**Other things I noticed, not part of the root cause:**
- Since the same deploy, `case_close_reminder` logs a `NoneType` error at `scheduled.py:47` (`datetime.utcnow() - case.triage_at`) every day. The `try` catches it, so only the affected case is skipped, but that case gets no reminder. The `stable_at` guard from `32fa810f` ("not all cases have a stable_at date") fixed the matching stable-case error, which stopped after the deploy. The triage path has no equivalent guard.
- The weekday check fails silently, with no log line when it skips, which is why nobody noticed quickly.

**Possible fix (not applied):** change `_is_reminder_day()` to `date.today().weekday() == calendar.MONDAY`, which is 0-based, or compare to `1` in ISO terms. I'd also add a `triage_at` guard matching the `stable_at` one. A regression test that pins `_is_reminder_day` to a known Monday would catch this class of bug. I did not change any code.

----- next turn -----

The weekly reminders are fixed, and there is a regression test that fails on the old code and passes on the new code. Nothing is committed.

**The fix** (`src/dispatch/case/scheduled.py`):
- `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches again. The old code compared `isoweekday()` (1 for Monday) against `calendar.MONDAY` (0), which is the bug from `c509d45e`.
- I also added the `if case.triage_at:` guard to `case_close_reminder`, matching the existing `stable_at` guard in the stable reminder. Without it, every triage case with no `triage_at` raised an error each day, and those cases never got the weekly reminder. This goes slightly beyond the weekday bug, but it sits in the same path, so I included it. Say if you'd rather it go in a separate change.

**The regression test** (`tests/case/test_case_scheduled.py`, new file):
- `_is_reminder_day` is checked for every day of the week with the date pinned, so Monday must return True and the other days False.
- `case_close_reminder` on a Monday with an 8-day-old triage case must send the reminder. The same case on a Tuesday must not.
- A triage case with `triage_at=None` must not send and must not raise.
- `case_stable_reminder` on a Monday with an 8-day-old stable case must send.
- The scheduler decorator opens its own engine across all organizations, so the test looks up the registered task by name and calls the undecorated function with the test session.

**Results:**
- Before the fix, the three Monday tests failed. `is_reminder_day(Monday)` returned False, and both reminder tests sent nothing.
- After the fix, `tests/case/test_case_scheduled.py` passes: 11 of 11.
- The full suite: 370 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way with my source change stashed, so they are unrelated to this fix.
- `ruff` isn't installed in this environment, so I didn't run lint or format checks. The new code follows the existing style in the file.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, so those cases get their Monday reminder. The new test covers it, and the tests pass. Nothing is committed.

**What causes the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. When `triage_at` is `None`, that raises the TypeError, and the job logs it once per affected case each evening. The last one in the logs is 2025-08-20.

`triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). That flow runs for New→Triage, Closed→Triage, and some other transitions. Any other transition into Triage hits the `(_, CaseStatus.triage)` branch at `flows.py:766`, which only logs a warning. The case ends up in Triage with no timestamp. The logs don't include the case IDs, and the warning doesn't appear in either log, so I haven't confirmed which transition produced the affected cases. The code path is the most likely cause.

**The change** (`src/dispatch/case/scheduled.py`):
- `case_close_reminder` now uses `triage_at or created_at` as the start of the count. The guard I added last turn is gone, so these cases are counted again instead of skipped.

**Tests** (`tests/case/test_case_scheduled.py`):
- I replaced the "skips when `triage_at` is missing" test with two tests:
  - A case with no `triage_at` and `created_at` 8 days ago gets the Monday reminder. This failed before the change and passes now.
  - A case with no `triage_at` and `created_at` 2 days ago gets no reminder.
- `tests/case/test_case_scheduled.py`: 12 of 12 pass.
- Full suite: 371 passed, 4 skipped, 8 failed. The same 8 tests fail with or without my changes, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`.

**Not changed:** `case_stable_reminder` still skips cases with no `stable_at`. You didn't ask about it, but it has the same gap. If you want it to count from `created_at` too, that's a small follow-up.

----- next turn -----

Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup. Two of them change behavior users would notice, and one is a unit change that looks like a regression. I did not change any code.

**Current windows, as the code applies them:**
- **Default dedup window** (when a signal has no dedup filter): **45 minutes**. It comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read in minutes. It matches only earlier instances of the same signal that already have a case and are not canaries (`signal/service.py:805`, `:812-815`).
- **Per-filter dedup window** (`SignalFilter.window`): **treated as seconds**, so `_window_start(f.window)` (`signal/service.py:845-846`). The column default is 3600 (the model comment says 1 hour, `signal/models.py:206-208`). The schema default is 600 (`models.py:282`). The UI labels the field "Window (minutes)" and offers 5, 10, 15, 20, 30 (`SignalFilterCreateDialog.vue:57`, `:196`). That value is saved unconverted.
- **Snooze**: no window. A filter snoozes until its `expiration` timestamp.

**The commits:**

1. **`a348bbd2`** (2025-05-29, Will Sheldon), "fix(signal): don't dedup on canary signals (#6026)"
   - Canary signal instances are skipped in dedup. Both the default path and the filter path add a `~canary` condition, and `filter_dedup` returns early for canary instances.
   - No window change.

2. **`7a9fe810`** (2025-06-19, Jordan Lee), "feat(signal): make the default deduplication window configurable"
   - The default dedup window was hard-coded to **1 hour**. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes** (`config.py`).
   - This is the default window's only change. The default is now 45 minutes instead of 60.

3. **`086dc910`** (2025-08-07, Sam Ortega), "refactor(signal): simplify snooze filter checks"
   - This is a behavior change, not only a refactor. In `filter_snooze`, an expired snooze used to hit `continue`, so the loop kept checking the remaining filters. It now hits `break`, which ends the loop. If an expired snooze is ordered before an active one, the active snooze is never evaluated, so the signal is not snoozed.
   - The early-exit checks for mode and action were also merged into one condition. That doesn't change behavior.

4. **`917a0b7b`** (2025-08-14, Jordan Lee), "refactor(signal): share the lookback window computation"
   - This is a unit change. Before, the per-filter window was `timedelta(minutes=f.window)`. Now it is `timedelta(seconds=f.window)`, and the code comment says it is stored in seconds.
   - The UI still labels the value as minutes and stores the raw number. Existing filters with values like 10 or 30 now look back 10 or 30 seconds, not minutes, which is 60 times shorter. The schema default of 600 now means 10 minutes, not 10 hours.
   - I can't confirm from the repo what values production filters actually have. This is worth checking before anything else.

No other commits since 2025-05-22 changed these paths. I searched the signal package, the config, and the repo history for `snooze`, `dedup`, `window`, `lookback`, and `duplicat`.

----- next turn -----

The cause was `917a0b7b` ("refactor(signal): share the lookback window computation"). It changed the per-filter window from minutes to seconds. A window of 30 then looked back 30 seconds, so two instances ten minutes apart could never be grouped. The fix puts the window back in minutes, which is what the UI shows, so existing filters work without edits. Nothing is committed.

**The fix:**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The per-filter window and the default dedup window both use it. The default window still comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, so 45 minutes by default, as before.
- `src/dispatch/signal/models.py`: the comment now says minutes. I also changed the column default from `60 * 60` to `60`. Under the minutes unit, `3600` would have meant 60 hours. The default only applies to rows created without a window, and the API always sends one, so this should change nothing in practice.

Stored values need no migration: 30 means 30 minutes, which is what the UI showed when users set it. The schema default (600) is unchanged, and it reads as minutes again, which is the meaning it had before `917a0b7b`.

**The regression test** (`tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_minutes`):
- A deduplicate filter with window 30 groups an instance that arrived 10 minutes earlier. This case failed before the fix and passes now.
- An instance 40 minutes earlier is not grouped, which confirms the window still applies.

**Test results:**
- `tests/signal`: 34 passed, 1 skipped.
- Full suite: 373 passed, 4 skipped, 8 failed. The same 8 tests fail with or without these changes, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`.

The other commit I listed, `086dc910` (`continue` changed to `break` in the snooze loop), is a separate issue and I did not change it. It doesn't cause this bug.

----- next turn -----

The cause was `086dc910` ("refactor(signal): simplify snooze filter checks"). In `filter_snooze`, an expired snooze used to hit `continue`, which moves on to the next filter. The commit changed it to `break`, which ends the loop. If the expired filter came first in `signal.filters`, the valid snooze was never checked, so the instance wasn't snoozed. The relationship has no `order_by`, so this depended on which row the database returned first.

**Fix** (`src/dispatch/signal/service.py`): restored `continue` for expired snooze filters. The rest of `086dc910`'s cleanup is kept, since that part didn't change behavior.

**Regression test** (`tests/signal/test_signal_service.py::test_filter_actions_snooze_skips_expired_filter`):
- The signal has two snooze filters on the same entity: one expired a week ago, added first, and one valid for 30 more days.
- The instance must come out as `snooze`.
- I checked the test both ways. With `break` it fails, and with `continue` it passes.

**Results:**
- `tests/signal`: 35 passed, 1 skipped.
- Full suite: 374 passed, 4 skipped, 8 failed. The 8 failures are the same ones as before, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail without my changes.

Nothing is committed. My working tree also still holds the earlier changes to the reminder code, the window unit fix, and their tests.

----- next turn -----

Here's the recap for the weekly report. Nothing is committed yet, and the changes are in the working tree.

**1. Weekly reminders never sent (weekday bug)**
- Cause: `_is_reminder_day()` compared `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check never passed. It was introduced when the check was moved into a helper and shipped in the 2025-08-13 deploy. Weekly close reminders for both triage and stable cases stopped from the Monday 2025-08-18 run. Daily triage reminders kept going.
- Fix: `date.today().weekday() == calendar.MONDAY`. Regression tests in `tests/case/test_case_scheduled.py` fail on the old code and pass on the fix.

**2. Nightly TypeError (missing triage timestamp)**
- Cause: `case_close_reminder` subtracted `triage_at` from the current time. `triage_at` is only set by `case_triage_status_flow`, and a transition into Triage that isn't in the status-flow match (`flows.py:766`) never sets it. Those cases hit the TypeError every evening.
- Fix: the job now counts from `triage_at`, falling back to `created_at` when it is missing, so those cases get their weekly reminder. Two tests cover this: an old case gets the reminder, and a recent case does not.
- Open: the logs don't include case IDs, so I couldn't confirm which transition produced the affected cases. `case_stable_reminder` still skips cases with no `stable_at`, which is a related gap I did not change.

**3. Dedup windows grouping too few instances**
- Cause: `917a0b7b` changed the per-filter window from minutes to seconds. The UI labels the field "Window (minutes)", so a 30-minute window became 30 seconds.
- Fix: the window is back in minutes, so existing stored values need no edit. The model's comment and column default were updated to match. A regression test checks a 30-minute window that groups an instance 10 minutes earlier and not one 40 minutes earlier.
- Open: I could not check the production filter values, so the size of the impact is unknown.

**4. Snoozes not applied when an expired filter came first**
- Cause: `086dc910` changed `continue` to `break` for expired snooze filters. Once it reached an expired filter, the loop stopped and never checked the valid one.
- Fix: restored `continue`. The rest of `086dc910`'s cleanup is kept. A regression test with an expired filter first fails with `break` and passes with `continue`.

**Test status:** the signal tests pass (35 passed, 1 skipped). The full suite has the same 8 failures as before, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail without these changes.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```