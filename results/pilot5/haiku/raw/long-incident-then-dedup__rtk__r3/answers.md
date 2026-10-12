**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 in Python (`calendar` uses 0-based weekdays). The comparison is therefore never true, so `_is_reminder_day()` returns False every day. The old inline check was `isoweekday() == 1`, which was correct. Because the helper is shared, both the long-running triage (`case_close_reminder`, line ~51) and stable (`case_stable_reminder`, line ~97) weekly reminders are suppressed. The daily `case_triage_reminder` does not use the helper, which is why those still arrive.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13T16:40:06Z (`scheduler.log:18851`) and the web pod at 16:40:07Z (`api.log:13201`). `c509d45e` is an ancestor of `81d8ae42`, and the previous image (`main-b05613b5`, deployed 2025-07-30) does not contain it. The logs show no other deploy between those two.

**Log evidence:**
- Monday 2025-08-11 (old code): close and stable reminders were sent (`scheduler.log:16799` onward).
- Monday 2025-08-18 (new code): no "Case close reminder sent" or stable reminder lines. Only the daily triage reminder and the incident reminders appear (`scheduler.log:25281`).

**Separate issue, not the cause:** `case_close_reminder` logs a `TypeError` (`datetime - NoneType`) for cases with `triage_at` unset (`scheduler.log:24277`, `25269`). It's caught per case, so other cases still process, but it's noisy and predates this change (first seen 2025-07-28). The stable reminder already guards `if case.stable_at:`, and the close reminder has no equivalent guard.

No code was changed. A minimal fix would be `date.today().weekday() == calendar.MONDAY` (or revert to `isoweekday() == 1`). That fix should also add a test that pins Monday to the helper, because the refactor's tests evidently didn't catch the off-by-one.

----- next turn -----

The Monday reminder bug is fixed, and there is a regression test that fails on the old code and passes on the fix. Nothing is committed.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use the 0-based numbering, so the check is true on Mondays. `isoweekday()` is 1-based and was the mismatch.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `date.today()` in the scheduled module and checks `_is_reminder_day()` for Monday 2025-08-11 through Sunday 2025-08-17. Only Monday is expected to return True.
- With the old line restored, the Monday case fails with `assert False is True`.
- With the fix, all 7 cases pass.

**Other tests:** `tests/case` and `tests/case_cost` pass (41 tests). I did not run the full suite.

**Environment problems:**
- `python -m pytest` failed at startup with `No module named 'devtools.pytest_plugin'`. The cause is `_bench_deps.pth` in the venv, which adds a directory outside the repo to the import path. I did not change that. I ran the tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_mock ...` instead. If your setup works with plain `python -m pytest`, that is the command to use.
- The venv had no pip and PyPI rejected the certificate. I installed the project with `uv pip install --native-tls -e ".[dev]"`.
- The test uses `mocker` from pytest-mock, so it needs that plugin loaded.

The unrelated `triage_at` `TypeError` in `case_close_reminder` from my earlier answer is still there. I left it alone because you asked only for the Monday fix.

----- next turn -----

The close-reminder `TypeError` is fixed, and the cases without a `triage_at` now count from `created_at`. I have not committed anything.

**Cause:** `triage_at` is only stamped in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`). That runs only for the New→Triage and Closed→Triage transitions through the dispatcher. Some paths set `status = triage` without stamping it:
- The reopen button handler (`src/dispatch/plugins/dispatch_slack/case/interactive.py:~1427`) sets the status directly and never calls the dispatcher.
- The dispatcher's catch-all `(_, triage)` branch (`flows.py:~766`) logs a warning and does not stamp `triage_at`. Stable→Triage and Escalated→Triage go through it.

The logs don't record which transition each affected case took, so I can't say from them which path produced the nulls. I did not change those paths, since you asked for the fallback only. Fixing them at the source would be a separate change.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the job now counts from `case.triage_at or case.created_at`. `created_at` is always set. The stable reminder already guards on `stable_at`, so I left it alone.

**Tests** (`tests/case/test_case_scheduled.py`, 3 new, 10 total in the file):
- A triage case with no `triage_at` and created 8 days ago gets the reminder. This is the regression case. Without the fix it fails.
- A triage case with no `triage_at` and created 2 days ago does not get one.
- When `triage_at` is set, it wins over `created_at`.

`tests/case` and `tests/case_cost` pass (44 tests). Same test command as before: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_mock ...`.

One detail for the tests: `scheduler.add` returns `None`, so the task can't be imported by name. The test looks it up in `scheduler.registered_tasks` instead.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 changed snooze or deduplication. Two of them changed the effective window, and one of those is a units change that affects existing filters. I have not changed any code.

**Windows as the code applies them today** (`src/dispatch/signal/service.py`)
- **Default dedup (signal has no dedup filters):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes** (`src/dispatch/config.py:95`). It can be overridden through the environment.
- **Custom dedup filter:** `SignalFilter.window`, in **seconds**. The `window` column defaults to 3600 (1 hour), and the Pydantic input model defaults to 600 (10 minutes).
- **Snooze:** no lookback window. A snooze is active until its `expiration` datetime, and an expression is optional.

**Commits**

1. **`a348bbd2`, 2025-05-29, Will Sheldon: "fix(signal): don't dedup on canary signals (#6026)"**
   - Canary signal instances are skipped by dedup. They are neither deduplicated nor used as the match for another instance. Both the default and the filter paths exclude them.
   - The default window was still 1 hour at this point.

2. **`7a9fe810`, 2025-06-19, Jordan Lee: "feat(signal): make the default deduplication window configurable"**
   - The default dedup window moved from a hard-coded **1 hour** to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes**.
   - The commit message says "configurable" and does not mention that the default value shrank from 60 to 45 minutes. Signals now dedupe over a shorter window unless the env var is set.
   - The `filter_signal` docstring still says "1-hour window".

3. **`086dc910`, 2025-08-07, Sam Ortega: "refactor(signal): simplify snooze filter checks"**
   - The snooze loop now skips filters whose mode is not active or whose action is not snooze, in one check. The warnings for a missing mode or action are gone.
   - Behavior change: when a snooze filter has expired, the loop now uses `break` where it used to use `continue`. Any snooze filters after the expired one are no longer checked.

4. **`917a0b7b`, 2025-08-14, Jordan Lee: "refactor(signal): share the lookback window computation"**
   - It added `_window_start(seconds)` and changed the custom dedup window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds.
   - This matches the model's comment ("number of seconds"). The old code treated the value as minutes.
   - **Impact:** existing filters with stored `window` values now dedupe over 60 times less time. For example, the 600 default becomes 10 minutes instead of 10 hours. The commit message does not mention the units change, and I found no migration that rescales stored values.

5. **`5e136d7b`, 2025-07-03, Alicia Matsumoto: "(feat) add entity and trigger views to signal instance page"**
   - This matched my keyword search, but I did not open its diff. From the message it is a UI change, not a dedup or snooze change.

Also `d2675cf4` (2025-07-03) and `4474af25` (2025-06-10) touch signal processing but do not show up in the dedup or snooze code. I did not inspect them further.

The stored-value impact in commit 4 is worth checking against production data before deciding how to handle it. It would take a query on `signal_filter.window` values.

----- next turn -----

The cause is commit `917a0b7b` (2025-08-14, Jordan Lee, "refactor(signal): share the lookback window computation"). It changed the custom dedup window from minutes to seconds. The UI stores the value as minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart fall outside that window, so the second one opened its own case.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. Both the custom filter window and the default window now pass minutes. Existing filters work without edits, because the stored values were already minutes.
- `src/dispatch/signal/models.py`: the column default is now 60 (minutes, same one hour as before) and the Pydantic default is now 10 (same ten minutes as before). Only new filters without an explicit window are affected by these two defaults.

**Regression test**
- `tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_in_minutes` has two cases on a filter with window 30. An instance 10 minutes earlier is deduplicated. One 40 minutes earlier is not.
- With the seconds conversion put back temporarily, the 10-minute case fails (`assert False is True`). With the fix in place it passes.
- The signal suite passes: 34 passed, 1 skipped.

**Full suite:** 371 passed, 8 failed, 4 skipped. The same 8 tests fail on a clean checkout of HEAD:
- six in `tests/ai/test_ai_service.py`
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data`
- `tests/entity/test_entity_service.py::test_find_entities_with_field_only`

I did not look into those eight.

**Not done**
- I didn't change the commit `7a9fe810` that set the default dedup window to 45 minutes (it was 60 before). That's a separate question.
- The docs still say "one hour" for the default window, and the `filter_signal` docstring does too. I left both.
- Nothing is committed. Plain `python -m pytest` still fails at startup in this environment, so I ran it as `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_mock`.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, Sam Ortega, "refactor(signal): simplify snooze filter checks"). In `filter_snooze`, the expired-filter check changed from `continue` to `break`. So the first expired snooze on a signal ended the loop, and the valid snooze listed after it was never checked. Instances for that user were not snoozed.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): the expired check goes back to `continue`. The mode/action refactor from that commit stays.

**Regression test** (`tests/signal/test_signal_service.py::test_filter_actions_snooze_expired_filter_does_not_stop_later_snooze`): an expired snooze is listed first, then a valid snooze, both matching the same entity. The instance must be snoozed. With `break` put back temporarily, the test fails; with the fix, it passes.

The signal suite passes: 35 passed, 1 skipped. I did not re-run the full suite this time. Last time, the same 8 tests failed on a clean HEAD, and they are unrelated to signals.

Nothing is committed. The working tree also still holds the earlier changes to `scheduled.py`, `models.py`, `service.py` and the test files.

----- next turn -----

## Recap

**Monday reminders (weekly close reminders not sent)**
- The cause is in `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` is 1-based (Monday is 1), but `calendar.MONDAY` is 0, so the check was never true. Commit `c509d45e` introduced it, and it shipped in image `main-81d8ae42`, deployed 2025-08-13.
- The fix uses `weekday()`, and a regression test checks Monday through Sunday.
- The first missed Monday was 2025-08-18.

**Case close reminder TypeError (evening job)**
- `case_close_reminder` subtracted `case.triage_at` from the current time. Some cases reach triage without `triage_at` being stamped. `case_triage_status_flow` only stamps it on New→Triage and Closed→Triage through the dispatcher. The reopen button and the catch-all `(_, triage)` branch skip it.
- The job now counts from `triage_at`, falling back to `created_at`. Three tests cover it.
- Not fixed: the paths that never stamp `triage_at`.

**Deduplication windows (signal "GuardDuty: Unauthorized API call")**
- Commit `917a0b7b` changed the custom window from minutes to seconds, so a UI window of 30 (minutes) became 30 seconds. The UI label has said "Window (minutes)" since 2023.
- The fix reads the window as minutes again, and the model defaults now match. Existing filters need no edits. A regression test covers a 30-minute window.

**Snoozing (signal "Okta: Impossible travel")**
- Commit `086dc910` changed `continue` to `break` for expired snooze filters in `filter_snooze`. An expired snooze ended the loop, so a valid snooze listed after it was never checked.
- The fix restores `continue`. A regression test covers an expired filter followed by a valid one.

**Status**
- Nothing is committed. All changes are in the working tree.
- The full suite has 8 failures that also occur on a clean HEAD, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. I did not investigate them.
- Commit `7a9fe810` also lowered the default dedup window from one hour to 45 minutes. The docs still say one hour. I did not change either.

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