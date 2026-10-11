**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. The refactor moved the check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's `weekday()` convention). I checked both values in the sandbox: `calendar.MONDAY = 0`, and Monday's `isoweekday()` is 1. So `_is_reminder_day()` is always False, and both `case_close_reminder` and `case_stable_reminder` never send. The original code compared against `1`, which was correct, so the refactor is the regression.

The daily triage reminders are unaffected because `case_triage_reminder` has no weekday check.

**Deploy that shipped it:** `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler and web pods at 2025-08-13 16:40 UTC (`api.log` line 13201, `scheduler.log` line 18851). That build includes `c509d45e`. The Monday 2025-08-11 run used the previous image (`main-b05613b5`) and still sent case close reminders. The first Monday on the new build, 2025-08-18, sent only the daily triage and incident close reminders. No case close or stable reminders went out.

**Secondary finding (not the cause):** the logs also show `TypeError: ... 'datetime.datetime' and 'NoneType'` in `case_stable_reminder` every day from 2025-07-28. `32fa810f` ("fix(scheduler): not all cases have a stable_at date", 2025-08-11, shipped in `81d8ae42`) added an `if case.stable_at:` guard. `case_close_reminder` still has the same unguarded `datetime.utcnow() - case.triage_at` at line 47 and logs a `TypeError` for cases with no `triage_at`. The per-case try/except keeps this from blocking other cases, so it is noise rather than the missed reminders.

**Suggested fix (not applied):** change `_is_reminder_day()` to compare against Monday in the same convention it uses, for example `date.today().weekday() == calendar.MONDAY`, or drop `calendar` and use `isoweekday() == 1` as before. A test that pins a known Monday date would have caught this.

----- next turn -----

The Monday reminders are fixed and there is a regression test for them. The full suite has 8 failures, and all 8 also fail on the untouched baseline.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both use Python's 0-based numbering, where Monday is 0. The previous `isoweekday()` is 1-based, so it never matched `calendar.MONDAY` (0).

**The regression test** (new file `tests/case/test_case_scheduled.py`):
- `_is_reminder_day()` returns True on a Monday and False on a Tuesday and a Sunday.
- `case_stable_reminder` and `case_close_reminder` each send a reminder for a week-old case on a Monday.
- `case_stable_reminder` sends nothing on a Tuesday.

The tests call the original task functions through `scheduler.registered_tasks`, because `scheduler.add` returns `None`, so the module-level names are `None`. They use fake case objects, so they don't need database rows.

**Verification:**
- Before the fix, the three Monday tests failed and the non-Monday tests passed.
- After the fix, all 6 tests in the new file pass, and `tests/case` passes (21 tests).
- Full `python -m pytest`: 365 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way on the baseline, so they are not from this change. I did not investigate them.

**Not done:** I did not commit or push. The unrelated `case_close_reminder` `triage_at` crash noted earlier is unchanged, since the task was only the Monday check.

----- next turn -----

The evening `TypeError` came from cases in Triage status with no `triage_at`. The close reminder now counts those cases from `created_at`, and a regression test covers it.

**Cause:** `case_triage_status_flow` is what sets `triage_at`. In `src/dispatch/case/flows.py:766`, the `(_, CaseStatus.triage)` branch of the status transition only logs a warning and never calls that flow. Any case that reaches Triage through that branch keeps `triage_at` NULL. `case_close_reminder` then runs `datetime.utcnow() - case.triage_at`, which raises the `TypeError` once per such case on each run. The logs show the error on every evening, which is consistent with a few stuck cases. I did not identify which transition created those specific cases, and I did not change the transition branch.

**Fix** (`src/dispatch/case/scheduled.py:47`): the job now uses `case.triage_at or case.created_at`. `created_at` is already loaded by `get_all_by_status`, so no query changed.

**Test** (`tests/case/test_case_scheduled.py`): `test_case_close_reminder_counts_from_created_at_without_triage_at` runs the job on a Monday with two cases that have no `triage_at`. One was created 8 days ago and gets a reminder. The other was created 2 days ago and does not. The test fails without the fix and passes with it.

**Verification:** the full suite gives 366 passed, 4 skipped, and the same 8 failures as before. Those failures also occur on the untouched baseline, so this change did not cause them. None of the changes are committed.

----- next turn -----



----- next turn -----

Since 2025-05-22, five commits changed the snooze or dedup decision in `src/dispatch/signal/`. Two of them change behavior without saying so in their messages. Nothing was modified.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29, Will Sheldon), "fix(signal): don't dedup on canary signals." Canary instances skip dedup entirely, and canary instances are excluded when matching against earlier instances. Snooze is unaffected.

2. **`7a9fe810`** (2025-06-19, Jordan Lee), "make the default deduplication window configurable." The default window for signals with no dedup filter was hard-coded as `timedelta(hours=1)`. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45, so the effective window dropped from 60 minutes to 45. The docs (`docs/docs/administration/settings/signal/filter.mdx:35`) and the `filter_signal` docstring still say one hour.

3. **`d2675cf4`** (2025-07-03, Sam Ortega), "mask sensitive raw fields before processing." This does not touch any window. It redacts `raw` before entity extraction, so entity-based snooze and dedup expressions now match against masked values. This is an indirect effect.

4. **`086dc910`** (2025-08-07, Sam Ortega), "simplify snooze filter checks." This was labelled a refactor but changed behavior. The `if f.expiration <= now` branch changed from `continue` to `break`. Once one snooze filter has expired, the loop stops, so later active snooze filters on the same signal are no longer evaluated. The warning logs for missing mode or action were also removed, and the missing-expiration case still continues.

5. **`917a0b7b`** (2025-08-14, Jordan Lee), "share the lookback window computation." This was also a behavior change hidden in a refactor. A custom dedup filter's `window` used to be applied as minutes (`timedelta(minutes=f.window)`). It is now applied as seconds (`_window_start(f.window)`). The column comment in `signal/models.py` already said seconds, so the code now matches it. A filter with `window=600` used to look back 10 hours and now looks back 10 minutes.

Two other signal commits in that range do not affect the decision: `4474af25` only adds logging, and `5e136d7b` is UI and schema work.

**Current values as the code applies them**

| Setting | Value | Unit |
|---|---|---|
| Default dedup window (no dedup filter) | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 | minutes (converted ×60 to seconds) |
| Custom dedup filter `window` | stored value, applied as seconds | seconds |
| `window` column default (`signal/models.py:206`) | 3600 | seconds (1 hour) |
| `window` schema default (`SignalFilterBase`, `signal/models.py:282`) | 600 | seconds (10 minutes) |
| Snooze | no time window; each filter has an `expiration` datetime | — |

Canary signals are exempt from dedup but not from snooze.

I did not query the database, so I can't say how many existing filters were stored with values that were meant as minutes. I also did not check how the UI sends the `window` value.

----- next turn -----

The cause was `917a0b7b` (2025-08-14, Jordan Lee, "refactor(signal): share the lookback window computation"). It changed the custom dedup window from minutes to seconds. The UI's "Window (minutes)" select sends 5, 10, 15, 20 or 30 as stored values. After the commit, a window of 30 was read as 30 seconds, so two instances ten minutes apart never matched and each opened a case.

**Fix**
- `src/dispatch/signal/service.py:845`: `filter_dedup` now uses `_window_start(f.window * 60)`, so the stored value is read as minutes again. Existing filters need no edits, because their stored values are already minutes.
- `src/dispatch/signal/models.py:206`: the column default changed from `60 * 60` to `60` and the comment now says minutes. Without this, the default would have become 60 hours.

**Tests** (`tests/signal/test_signal_service.py`)
- `test_filter_actions_deduplicate_window_is_in_minutes` is the regression test. It has two instances ten minutes apart with a window of 30 and expects deduplication. It fails without the fix.
- `test_filter_actions_deduplicate_window_expires` covers the other direction: a window of 5 does not match an instance ten minutes old.

**Results:** the signal service tests pass (16 passed, 1 skipped). The full suite has 368 passed, 4 skipped and the same 8 failures as before, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They also fail on the untouched baseline and I have not investigated them. Nothing is committed.

**Left unchanged, for you to decide**
- The schema default in `SignalFilterBase` (`signal/models.py:282`) is still `600`. Before 2025-08-14 it meant 600 minutes, and it still does now. New filters created through the API without a window therefore get a 10-hour window. Changing it would change behavior for those new filters, so I did not.
- The docs (`docs/docs/administration/settings/signal/filter.mdx:35`) and the `filter_signal` docstring still say one hour. Those match the 1-hour default in the model.

----- next turn -----

The cause was `086dc910` (2025-08-07, Sam Ortega, "refactor(signal): simplify snooze filter checks"). In `filter_snooze`, an expired snooze filter changed from `continue` to `break`. Once the loop reached an expired filter, it stopped, so any valid snooze filter listed after it was never checked. For "Okta: Impossible travel", the expired filter is listed first, so new instances for that user were not snoozed.

**Fix:** `src/dispatch/signal/service.py:763` now uses `continue` for expired filters, as it did before `086dc910`. No data changes are needed.

**Regression test:** `test_filter_actions_snooze_after_expired_filter` in `tests/signal/test_signal_service.py`. It has an expired snooze filter listed first and a valid one after it, and expects the instance to be snoozed. It fails when `break` is restored and passes with the fix.

**Results:** the signal service tests pass (17 passed, 1 skipped). The full suite has 369 passed, 4 skipped, and the same 8 failures as before, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. Those were already failing on the untouched baseline. Nothing is committed.

----- next turn -----

**Monday weekly reminders**

Assignees stopped getting the Monday reminders for long-running triage and stable cases after the scheduler and web pods started on image `main-81d8ae42` on 2025-08-13. Daily reminders kept working. The cause is that `_is_reminder_day()` compared `date.today().isoweekday()`, which is 1-based with Monday as 1, against `calendar.MONDAY`, which is 0. The comparison was never true. Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") introduced it. The fix uses `weekday()`. Two regression tests cover the Monday check. The Monday 2025-08-11 run had already sent reminders, so the first missed Monday was 2025-08-18.

**Evening TypeError in the case close reminder**

`case_close_reminder` ran `datetime.utcnow() - case.triage_at` for every case in Triage. Some cases in Triage have no `triage_at`, because the `(_, CaseStatus.triage)` transition branch in `src/dispatch/case/flows.py` never calls `case_triage_status_flow`, which is what sets it. Each such case raised a TypeError on each nightly run. The job now counts from `created_at` when `triage_at` is missing, and a test covers this. I did not identify which transition left those specific cases without a timestamp, and I did not change the flow branch.

**Signal deduplication and snoozing**

Three commits changed signal behavior in ways you may want to report:

- **Canary signals** (`a348bbd2`, 2025-05-29): canary instances are excluded from deduplication.
- **Default dedup window** (`7a9fe810`, 2025-06-19): the hard-coded one-hour window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45, so the effective window dropped to 45 minutes.
- **Custom dedup window unit** (`917a0b7b`, 2025-08-14): a filter's window, set in minutes in the UI, was read as seconds. A window of 30 covered only 30 seconds, so instances ten minutes apart opened separate cases. The fix reads it as minutes again, and existing filters work unchanged. The column default changed from 3600 to 60 to match the one-hour comment.
- **Snooze after an expired filter** (`086dc910`, 2025-08-07): an expired snooze filter stopped the loop with `break`, so valid filters listed after it were never checked. The fix uses `continue`, which restores the previous behavior.

Each fix has a regression test that fails without it. The signal tests pass. The full suite has 369 passed, 4 skipped, and 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. Those 8 also fail on the untouched baseline and were not investigated.

**Open items**
- The schema default for a new filter's window, 600 in `SignalFilterBase`, is now read as 600 minutes (10 hours). That was also true before the August change. I did not change it.
- Nothing is committed.

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