The root cause is a one-line bug in the refactor commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It shipped to production in image `main-81d8ae42` on 2025-08-13 at 16:40 UTC, when the scheduler pod started. I haven't changed any code.

**Root cause**

`src/dispatch/case/scheduled.py:33` now reads:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 in Python. The check is therefore always false, so `case_close_reminder` and `case_stable_reminder` never send the weekly reminder. The old code compared against the literal `1`, which was correct. The daily triage reminder (`case_triage_reminder`) has no weekday check, so it keeps working. This matches the logs:

- Monday 2025-08-11 18:00 UTC: "Case close reminder sent" for several assignees, before the deploy.
- Monday 2025-08-18 18:00 UTC: no case close reminders. Only the incident close reminder ran, and that path is separate.
- Daily triage reminders continue throughout.

The bug is still on `main` at HEAD (`20f33137` through `51546e13`, 2025-09-02), so the line has not been fixed.

**Deploy that shipped it**

- Commit `c509d45e` is an ancestor of `81d8ae42` ("fix(case): exclude resolved_by in update", 2025-08-12). `81d8ae42` is the image that the web and scheduler pods started on 2025-08-13.
- The scheduler log shows `scheduler-mhtsgqwwx-q5q2n` starting `main-81d8ae42` at 16:40:06 UTC on 2025-08-13, replacing the previous pod that ran `main-b05613b5`.

**Separate issues in the logs (not the cause)**

- `case_stable_reminder` crashed on `case.stable_at = None` every day from 2025-07-28 to 2025-08-12. Commit `32fa810f` (2025-08-11) added the `if case.stable_at:` guard, which is why those errors stop after 08-12.
- `case_close_reminder` still logs a per-case `TypeError` for `case.triage_at = None` (now at `scheduled.py:47`, logged at line 55). The exception is caught per case, so other cases are unaffected. It is still worth fixing.

A likely fix is to compare against `1` (or `calendar.MONDAY + 1`) in `_is_reminder_day()`, and to add a test that pins it to a real Monday. I can make that change when you say so.

----- next turn -----

Fixed, with a regression test. The change is uncommitted in the working tree.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY` instead of `isoweekday()`. Both `weekday()` and `calendar.MONDAY` are 0-based, so the comparison is correct and still uses the named constant.

**Regression test** (new file `tests/case/test_case_scheduled.py`): a parametrized test that mocks `date.today()` for each day of the week from Monday 2025-08-18 through Sunday 2025-08-24, and asserts `_is_reminder_day()` returns true only on Monday.

**Verification**
- With the fix: the new file passes, 7/7. `python -m pytest tests/case` passes, 22/22.
- Against the old code (temporarily stashed): the Monday case fails and the other six pass, so the test catches the bug.

I only ran `tests/case`, not the full suite. The fix only touches this one helper, but if you want a wider check, the full `python -m pytest` run is the next step. I haven't committed anything.

----- next turn -----

The job's `TypeError` comes from cases that are in `triage` but have no `triage_at` timestamp. The job subtracts that NULL from the current time, so every such case fails. The fix counts from `created_at` in that case, and the new tests cover it. Nothing is committed.

**Cause**

`triage_at` is only set by `case_triage_status_flow`. Some paths put a case into `triage` without running that flow, so the timestamp is never written:

- The Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1425-1427`) sets `case.status = CaseStatus.triage` and calls no transition flow at all.
- The 2022 migration that added `triage_at` (`391f7c3e6992`) made the column nullable and did not backfill existing rows, so legacy cases that were in triage at the time keep NULL.

The logs have no case IDs, so I can't tell which of these produced the rows in your database. To see which applies, run this in each tenant schema:

```sql
SELECT id, created_at FROM "case" WHERE status = 'triage' AND triage_at IS NULL;
```

If the rows are old, the migration is the cause. If they were reopened, it's the reopen button.

**Fix** (`src/dispatch/case/scheduled.py:47-49`): the job now counts from `case.triage_at or case.created_at`. A case with a recorded `triage_at` is unchanged.

**Tests** (`tests/case/test_case_scheduled.py`): the job is called through the scheduler registry with the reminder day forced on:
- No `triage_at`, created 8 days ago: the reminder is sent.
- No `triage_at`, created 2 days ago: no reminder.
- `triage_at` 2 days ago and created 30 days ago: no reminder, so `triage_at` takes precedence.

With the old line restored, the first test fails with the same `TypeError` as production. With the fix, `python -m pytest tests/case` passes, 25/25.

**Not changed:** `case_stable_reminder` already skips cases with a NULL `stable_at`, so cases in that state get no weekly reminder. If you want the same fallback there, I can make that change next.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or dedup behavior. Two of them change the time windows. I haven't changed any code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals". Canary signal instances skip deduplication entirely, and they are also excluded from the instances that dedup matches against, in both the default and filter paths. No time window involved.

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable". The default window for signals with no dedup filter was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, default **45 minutes** (env-overridable, unit minutes).

3. **`086dc910`** (2025-08-07), "simplify snooze filter checks". Two behavior changes in `filter_snooze`:
   - An expired snooze filter was skipped with `continue`. It now ends the loop with `break`, so later snooze filters on the same signal are no longer checked after an expired one. This is a behavior change, though the commit message calls it a refactor.
   - The mode, action, and expiration checks are merged into one condition. The `log.warning` calls for missing mode or action are gone. Missing expiration still logs a warning and is skipped.
   
   Snooze has no lookback window. It applies while `expiration` is in the future.

4. **`917a0b7b`** (2025-08-14), "share the lookback window computation". This changed the unit of the per-filter dedup window. The code used to treat `SignalFilter.window` as **minutes** (`timedelta(minutes=f.window)`). It now treats it as **seconds** (`_window_start(f.window)`, with the comment "SignalFilter.window is stored in seconds"). The `SignalFilter` column default (`src/dispatch/signal/models.py:206`) is `60 * 60`, which is seconds. So:
   - The model default went from 3600 minutes (2.5 days) to **1 hour**.
   - The schema default `SignalFilterBase.window = 600` (`models.py:282`) went from 600 minutes (10 hours) to **10 minutes**.
   - Existing stored `window` values were not migrated. I found no migration in the range, so any filter saved with a minutes value now has a window 60 times shorter.

**Current values**

- Default dedup (no dedup filter on the signal): 45 minutes, matched against instances with a case.
- Dedup filter: `SignalFilter.window` in seconds. The DB default is 3600 (1 hour). The API schema default is 600 (10 minutes).
- Snooze: no lookback window. It lasts until `SignalFilter.expiration`.

The `filter_signal` docstring still says "1-hour window", which is stale. The default is 45 minutes.

The window change in `917a0b7b` is the likely candidate for "changed how dedup works" if any filters were created before 2025-08-14. Existing filters created under the minutes assumption now behave as if their windows were 60 times shorter. I haven't checked a database for filter rows, so I can't say how many are affected.

----- next turn -----

The window bug came from `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the unit of `SignalFilter.window` from minutes to seconds. The UI labels the field "Window (minutes)" and offers 5 to 30. So a 30 now means 30 seconds, and two instances ten minutes apart fall outside it and open two cases. The other three commits don't touch filter windows.

**Fix**

- `src/dispatch/signal/service.py`: `_window_start` takes minutes again, and both the filter window and the default dedup window pass minutes. Existing filters work unedited because their stored values were always minutes, as the UI entered them.
- `src/dispatch/signal/models.py:206-208`: the column default is now `60` minutes, with a comment that says minutes. The comment already said "1 hour", so I went with 60. Before `917a0b7b` the effective default was 3600 minutes, so this changes what a filter created without a window gets. Tell me if you'd rather keep 3600.

**Regression test**

`test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. An earlier instance for the same entity, ten minutes ago, opened a case. A new instance with a window of 30 must dedupe to that case. It failed on the seconds code (`assert False`) and passes now.

**Test results**

- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- `python -m pytest` (full suite): 370 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). I ran those files on a clean checkout of HEAD, and the same 8 fail there, so they predate these changes.

**Left alone**

- `SignalFilterBase.window = 600` in `models.py` is now 600 minutes (10 hours), which is what it has always meant before `917a0b7b`.
- The `filter_signal` docstring still says "1-hour window". The default is 45 minutes.
- Nothing is committed. The working tree also still has the earlier case-close-reminder changes.

----- next turn -----

The cause is the `continue` → `break` change in `086dc910` (2025-08-07, "simplify snooze filter checks"). In `filter_snooze`, an expired snooze filter used to be skipped with `continue`. The commit changed that to `break`. The loop then stops at the first expired filter, so any valid snooze filter listed after it is never checked. For the Okta signal, the expired filter comes first, so new instances for that user are not snoozed.

**Fix**

`src/dispatch/signal/service.py`: restored `continue` for expired filters in `filter_snooze`. The rest of that commit's simplification is still in place.

**Regression test**

`test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It puts an expired snooze filter before a valid one for the same entity, then asserts the instance is snoozed. It failed on the `break` code and passes now.

**Test results**

- `python -m pytest tests/signal`: 34 passed, 1 skipped.
- `python -m pytest` (full suite): 371 passed, 4 skipped, 8 failed. The 8 failures are the same ones that fail on a clean HEAD (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`), so they are not from these changes.

Nothing is committed. The working tree also has the earlier changes to `src/dispatch/case/scheduled.py`, `src/dispatch/signal/models.py`, `src/dispatch/signal/service.py` (the minutes fix), and the test files.

----- next turn -----

Here is the recap for both investigations. Nothing is committed yet. All changes are in the working tree.

**Weekly reminders (weekday bug)**

Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The new check compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, while `calendar.MONDAY` is 0, so the check was never true. Weekly close and stable reminders stopped. Daily triage reminders don't use this check, so they kept working. The commit was in the image deployed on 2025-08-13 16:40 UTC (`main-81d8ae42`, web and scheduler). The first Monday without reminders was 2025-08-18.

Fix: `_is_reminder_day()` uses `date.today().weekday() == calendar.MONDAY`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`, parametrized over a Monday and each other day of the week.

**Evening TypeError (case close reminder)**

`case_close_reminder` subtracts `case.triage_at` from the current time. Some cases in `triage` have no `triage_at`, so the subtraction raises a TypeError every evening. `triage_at` is only set when the triage flow runs. The Slack reopen button sets the status without running it, and legacy rows from the 2022 migration were never backfilled. The logs have no case IDs, so I haven't confirmed which path produced the rows in your database.

Fix: the job counts from `triage_at or created_at`, so those cases get their weekly reminder. Tests cover a missing `triage_at` with an old case (reminder sent), a recent case (no reminder), and a `triage_at` that takes precedence over `created_at`.

**Deduplication windows (window units)**

Commit `917a0b7b` (2025-08-14, "share the lookback window computation") changed `SignalFilter.window` from minutes to seconds. The UI labels the field "Window (minutes)", so a window of 30 was effectively 30 seconds. Two instances ten minutes apart opened two cases. Fix: the window is read as minutes again, the column default is 60 minutes, and the default-window path passes minutes. Existing filters work without edits. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.

**Snoozing (expired filter stops the check)**

Commit `086dc910` (2025-08-07, "simplify snooze filter checks") changed the expired-filter branch in `filter_snooze` from `continue` to `break`. An expired snooze filter now stopped the loop, so a valid filter listed after it never ran. Fix: restored `continue`. Regression test: `test_filter_actions_snooze_skips_expired_filter`, with the expired filter listed first.

**Canary signals**

Commit `a348bbd2` (2025-05-29, "don't dedup on canary signals") is the commit that changed canary deduplication. It skips dedup for canary instances and excludes them from matching.

**Test status**

`python -m pytest` runs 371 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way on a clean checkout of HEAD, so they predate these changes. I did not investigate them.

**Open items**

- The `triage_at` cause is not confirmed against your database. Run `SELECT id, created_at FROM "case" WHERE status = 'triage' AND triage_at IS NULL;` in each tenant schema to see which path produced the rows.
- The `case_stable_reminder` job still skips cases with no `stable_at`. I did not change that.
- The `SignalFilterBase.window` default is still 600, which is now 600 minutes (10 hours), as it was before `917a0b7b`.
- The `filter_signal` docstring still says "1-hour window". The default is 45 minutes.

```
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
```