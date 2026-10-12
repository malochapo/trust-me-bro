**Root cause:** the weekly Monday check compares against the wrong constant. `calendar.MONDAY` is `0`, because Python's `calendar` numbers weeks from Monday = 0. But the check is `date.today().isoweekday() == calendar.MONDAY`, and `isoweekday()` returns 1 for Monday. So the condition is never true, and the weekly close reminders for triage and stable cases are never sent. The daily triage reminder doesn't go through this check, so it keeps running.

**Where it came from:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12, 14:05 PDT). The original code was `date.today().isoweekday() == 1`, which was correct. The refactor moved it into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` and wrote `calendar.MONDAY` instead of `1`. The bad line is `src/dispatch/case/scheduled.py:33`, and it is used at lines 49 and 95.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. That is commit `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)", 2025-08-12 14:47 PDT), which contains `c509d45e`. The web and scheduler containers both started on that image at 2025-08-13 16:40 UTC (`api.log:13201`, `scheduler.log:18851`).

**Log evidence:**
- Monday 2025-07-28, 08-04 and 08-11 each sent case close reminders (4, 6 and 5 sends). 08-11 ran before the refactor landed.
- The first Monday on the new image was 2025-08-18. The scheduler ran at 18:00, and the triage reminders went out, but there were no "Case close reminder sent" lines at all.

**Related issue, not the cause:** commit `32fa810f` fixed the `stable_at is None` crash in `case_stable_reminder`. The `case_close_reminder` path still logs a `NoneType` TypeError on `case.triage_at` (line 47) for some cases on 08-18. That error is caught per case, so it skips those cases and does not stop the rest, but it's still worth fixing separately.

**Fix (not applied, since you asked me not to change code):** use `date.today().weekday() == calendar.MONDAY`, which is 0-based, or restore `date.today().isoweekday() == 1`. A regression test that pins the Monday check would catch this, since the bug only shows up on a real Monday.

I couldn't check the scheduler's own deploy history beyond the container start events in these logs, so the image-to-commit mapping for the scheduler is based on those start events.

----- next turn -----

The weekly Monday reminders are fixed, and a regression test is in place. The test fails on the buggy code and passes with the fix.

**The fix** is one line in `src/dispatch/case/scheduled.py:33`. `calendar.MONDAY` is 0 and `isoweekday()` is 1-based, so the check now uses `date.today().weekday()`, which is also 0-based. Nothing else changed.

**The regression test** is `tests/case/test_case_scheduled.py`. It pins `date.today()` to each day of one week (Aug 18–24, 2025) and asserts that `_is_reminder_day()` is true only on Monday. I used a patched `date` class because freezegun isn't installed. Results:
- Against the buggy code, the Monday case fails: `1 failed, 6 passed`.
- With the fix, `7 passed`.
- `python -m pytest tests/case` passes: 22 tests.

I didn't commit anything. Ruff isn't installed in this environment, so I didn't lint.

The `NoneType` crash on `case.triage_at` in `case_close_reminder` is still there. It's logged per case and doesn't stop the other cases, but it's a separate bug and I didn't touch it.

----- next turn -----

The close reminder job now counts from `created_at` when `triage_at` is missing, so those cases get their weekly reminder. The new tests pass, and the one that covers this fails on the original code.

**What causes the TypeError:** `case_close_reminder` does `datetime.utcnow() - case.triage_at`. Some cases still in triage have `triage_at = NULL`, and subtracting `None` raises the logged error. The per-case `try` catches it, so the other cases still run, but these cases never get a reminder. The column was added in migration `2022-08-01_391f7c3e6992` with no backfill, and it's only set by `case_triage_status_flow` (`src/dispatch/case/flows.py:592-596`).

I couldn't identify the specific affected cases. The logs have no case IDs, and I don't have database access. The create paths all go through the triage flow, so the nulls come from status changes that don't reach that flow. The likeliest candidates are cases that moved into triage from escalated or stable, or cases from before the 2022 migration. Finding the exact ones needs a query against the database.

**The fix** is in `src/dispatch/case/scheduled.py:47-48`: `span = datetime.utcnow() - (case.triage_at or case.created_at)`. I left the flow code alone. Fixing the transitions that skip `triage_at` would be a separate change.

**Tests** are in `tests/case/test_case_scheduled.py`. They call the job through the scheduler registry, so they exercise the real loop:
- A case with no `triage_at`, created 8 days ago, gets a reminder on a Monday. This test fails on the original code with the same TypeError.
- A case with no `triage_at`, created 3 days ago, gets no reminder.
- When `triage_at` is set (8 days ago) and `created_at` is recent, the reminder still uses `triage_at`.

`python -m pytest tests/case` passes: 25 tests.

The stable reminder has the same kind of gap, but its `if case.stable_at:` guard skips those cases rather than counting from `created_at`. I left it as it is. Say if you want it changed to match.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four are in `src/dispatch/signal/service.py`. None changed the snooze lookback, because snooze has no time window: it matches any instance of the signal whose expression matches, subject to the filter's expiration.

| Commit | Date | Author | What it changed |
|---|---|---|---|
| `a348bbd2` | 2025-05-29 | Will Sheldon | `filter_dedup` returns early for canary signal instances, and canary instances are excluded from the match queries in both the default and per-filter dedup paths. |
| `7a9fe810` | 2025-06-19 | Jordan Lee | The default dedup window (applied to signals with no dedup filter) became configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, defaulting to 45 minutes. It was hard-coded at 1 hour before. |
| `086dc910` | 2025-08-07 | Sam Ortega | `filter_snooze` simplified. An expired snooze filter now `break`s out of the loop, where it used to `continue`, so any later active snooze filters are no longer evaluated. The "no mode" and "no action" warnings were removed. |
| `917a0b7b` | 2025-08-14 | Jordan Lee | Added `_window_start`. The per-filter dedup window is now read as **seconds**, where it was previously `timedelta(minutes=f.window)`. The commit message doesn't mention this unit change. |

Current values as the code applies them:

- **Default dedup window** (no dedup filter on the signal): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` × 60, so 45 minutes (2700 seconds) by default. It is the only dedup window in minutes.
- **Per-filter dedup window** (`SignalFilter.window`): a count of seconds, used as-is. The model default is 3600 seconds (1 hour). The API schema default (`SignalFilterBase.window`) is 600 seconds (10 minutes). The two defaults disagree.
- **Snooze**: no lookback window. Expiration is checked against `datetime.now(timezone.utc)`, and filters with no expiration are skipped with a warning.

The unit change in `917a0b7b` matters for existing data. A dedup filter that stored `window=600` meant 600 minutes (10 hours) before 2025-08-14 and means 600 seconds (10 minutes) now. I didn't check whether a data migration rescaled stored values. If none did, dedup filters created before that date are now much narrower than their owners intended.

Commits I excluded because they don't affect the decision: `d2675cf4` (masks raw fields before processing), `4474af25` (logs outcomes), and `5e136d7b` (UI views).

I didn't change any code.

----- next turn -----

The cause is commit `917a0b7b` (Aug 14, "refactor(signal): share the lookback window computation"). It changed the per-filter dedup window from minutes to seconds. The UI labels the field "Window (minutes)" with options 5–30, so a window of 30 was read as 30 seconds, and two instances ten minutes apart fell outside it. The other commits I listed don't affect this window.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The per-filter window is read as minutes again, and the default dedup window passes its minutes value directly.
- `src/dispatch/signal/models.py`: the model's `window` default is now `60` (minutes), so the comment's "1 hour" is true. It was `60 * 60`, which would have meant 60 hours under the minutes reading.

Existing filters need no edits. Their stored values were already entered in minutes through the UI, so they now mean what the UI says.

**Regression tests** in `tests/signal/test_signal_service.py`:
- `test_filter_window_is_in_minutes`: a 30-minute window groups two instances ten minutes apart. It fails when I put the seconds reading back, and passes with the fix.
- `test_filter_window_excludes_instances_outside_minutes`: an instance 40 minutes old is outside a 30-minute window and is not grouped.

**Test results**
- `python -m pytest tests/signal`: 34 passed, 1 skipped.
- Full `python -m pytest`: 371 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those eight on the original code, and they fail there too. They predate this work and I did not investigate them.

**Things I did not change**
- The API schema default for `SignalFilterBase.window` is still `600`. Under the minutes reading, that is 10 hours. That matches the behaviour before Aug 14, but it is probably not what was intended. Changing it would change what the API stores for filters created without a window, so I left it for you to decide.
- `086dc910` still `break`s out of the snooze loop on an expired filter, so later active snooze filters are skipped. That is a separate behaviour change and I left it alone.
- Commits aren't made. The working tree has my changes plus the earlier `scheduled.py` changes and the untracked `tests/case/test_case_scheduled.py`.

----- next turn -----

The cause is commit `086dc910` (Aug 7, "refactor(signal): simplify snooze filter checks"). In `filter_snooze`, the expired-filter check changed from `continue` to `break`. An expired snooze filter that comes before a valid one in the filter list therefore stops the loop, and the valid filter is never checked. New instances for that user go unsnoozed.

**Fix:** in `src/dispatch/signal/service.py`, the expired-filter branch of `filter_snooze` now uses `continue`, as it did before `086dc910`. The rest of that commit's simplification is kept.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It puts an expired snooze filter first and a valid one (30 days out) second, both matching the same entity. It asserts the instance is snoozed. The test fails with `break` and passes with `continue`.

**Test results**
- `python -m pytest tests/signal`: 35 passed, 1 skipped.
- Full `python -m pytest`: 372 passed, 4 skipped, 8 failed. The 8 failures are the same ones as before (`tests/ai/test_ai_service.py` ×6, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`). They also fail on the original code, so they predate this change.

Nothing is committed. The working tree also still holds the earlier changes to `scheduled.py`, `models.py`, and the window fix in `service.py`.

----- next turn -----

## Recap

**Weekly reminders (Monday).** Assignees stopped getting weekly reminders to close long-running triage and stable cases after the deploy of 2025-08-13. The cause was `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") introduced the mismatch, and it shipped in image `main-81d8ae42`. The fix uses `weekday()`. A regression test in `tests/case/test_case_scheduled.py` fails on the old code and passes with the fix.

**Evening TypeError.** The close-reminder job did `datetime.utcnow() - case.triage_at`. Cases in triage with no `triage_at` raised a TypeError, which the per-case `try` caught, so those cases never got a reminder. The job now counts from `created_at` when `triage_at` is missing. Three job-level tests cover it: the missing-field case fails on the old code, a recent case is skipped, and a set `triage_at` still wins. The root cause of the null `triage_at` rows is not confirmed. The logs have no case IDs, and I had no database access. The likely paths are transitions into triage that skip `case_triage_status_flow`, and cases from before the 2022 column was added.

**Deduplication windows.** The UI labels a filter's window "minutes", but commit `917a0b7b` (2025-08-14) started reading it as seconds. A 30-minute window became 30 seconds. The fix restores minutes and corrects the model default and comment. Two regression tests cover it: one that groups instances ten minutes apart, and one that excludes an instance 40 minutes old. The first fails with the seconds reading.

**Snoozing.** Commit `086dc910` (2025-08-07) changed the expired-filter check in `filter_snooze` from `continue` to `break`. An expired snooze filter ahead of a valid one stopped the loop, so the valid one never applied. The fix restores `continue`. A regression test puts an expired filter first and a valid one second. It fails with `break` and passes with `continue`.

**Test status.** `python -m pytest` gives 372 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail on the original code, so they predate this work. Nothing is committed. The working tree has the changes to `src/dispatch/case/scheduled.py`, `src/dispatch/signal/models.py`, `src/dispatch/signal/service.py`, `tests/signal/test_signal_service.py`, and the new `tests/case/test_case_scheduled.py`.

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