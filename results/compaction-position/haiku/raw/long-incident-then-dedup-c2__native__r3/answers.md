**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the Monday check with `_is_reminder_day()`, which compares against `calendar.MONDAY`. That constant is `0` in Python (Monday-is-0 convention), but `date.today().isoweekday()` returns `1` on Monday. So `_is_reminder_day()` is never true, and both weekly reminders are suppressed. The daily triage reminder has no weekday check, which is why it still arrives.

**Where it is:** `src/dispatch/case/scheduled.py:31-33`:
```python
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY   # 1 == 0 is always False
```
It is called from `case_close_reminder` (line 49) and `case_stable_reminder` (line 95). The old code compared against the literal `1`, which was correct. The refactor replaced it with the wrong constant.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out at 2025-08-13 16:40 UTC to both the web and scheduler pods (`scheduler.log:18851`, `api.log:13201`). That tag is commit `81d8ae42` (#6183), and `c509d45e` is earlier on main in the same batch, so the image should contain it. I inferred that from the tag and history rather than checking the image contents.

**Evidence from the logs:**
- Monday 2025-08-11 (before the deploy): `case_close_reminder` sent 5 close reminders and `case_stable_reminder` sent at least one (k.tanaka).
- Monday 2025-08-18 (after): 0 close reminders sent; the stable job finished in 0.03s with no sends.
- After 2025-08-13, no close reminders were sent on any day, and triage reminders kept going out daily.
- The Python check confirms `calendar.MONDAY == 0` and `date(2025,8,18).isoweekday() == 1`.

**Ruled out:**
- The `stable_at` `TypeError` in `case_stable_reminder` (logged daily from 07-28 to 08-12) was a real bug but not this one. It was fixed in `32fa810f` (08-11), which shipped in the 08-13 deploy. After 08-13 there are no `stable_at` errors. It did not stop Monday reminders on 08-11, because the `if case.stable_at` guard only skips cases with no date.
- `81d8ae42` itself (exclude `resolved_by` in case update) does not touch reminders. It is only the deploy tag.

**Side finding, not the cause:** `case_close_reminder` still raises `TypeError` on `case.triage_at is None` (`scheduled.py:47`, e.g. `scheduler.log` 2025-08-18). That error is per-case and caught, so it doesn't break the job, but it means those cases are skipped. It is a separate bug worth a follow-up.

I didn't change any code. A fix would be to compare `_is_reminder_day()` against `1` (or to use `calendar.MONDAY` consistently with `date.weekday()`, which is 0-based, instead of `isoweekday()`). A test that pins a known Monday would catch this regression.

----- next turn -----

I fixed the weekly reminder bug and added a regression test. The case suite passes (19 tests), and the new test fails on the old code.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches. The old `isoweekday()` returns 1 for Monday, which never equals `calendar.MONDAY` (0).

**The regression test** (`tests/case/test_case_scheduled.py`, new file): it pins "today" to a Monday, a Sunday, a Tuesday, and a Friday, and checks that only the Monday returns true. I patched `date` in the module because the repo has no freezing library. Against the old line, the Monday case fails. Against the fix, all four pass.

**Tests run:**
- `python -m pytest tests/case/test_case_scheduled.py`: 4 passed
- `python -m pytest tests/case`: 19 passed

I didn't run the full suite. I also didn't check the Monday behaviour end to end against the local PostgreSQL. The unit test covers the broken function directly.

The change is uncommitted in the working tree. I didn't commit it, since you only asked for the fix.

----- next turn -----



----- next turn -----

The evening `TypeError` comes from `case_close_reminder` subtracting `case.triage_at` when it is `None`. The fallback is in place, and the new tests pass.

**Cause:** `triage_at` is only stamped by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). The Slack reopen button handler, `reopen_button_click` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`), sets `case.status = CaseStatus.triage` directly and never runs that flow. A case that was closed from `new` and then reopened therefore reaches triage with `triage_at` still empty. The logs have 80 of these errors but no case IDs, so I matched the error to this code path rather than to specific cases.

**Fix** (`src/dispatch/case/scheduled.py:47`): the job now counts from `case.triage_at or case.created_at`, so those cases get their weekly reminder once they're more than a week old.

**Tests** (`tests/case/test_case_scheduled.py`): two new tests run the real `case_close_reminder` job with patched data.
- A case with no `triage_at`, created 8 days ago, gets the reminder. A case created 2 days ago does not.
- When `triage_at` is set, the job still counts from it, as before.

Without the fallback, the first test fails with the same `TypeError`. `python -m pytest tests/case` passes (21 tests), and I restored the fix after that check.

**Not changed:**
- The reopen button handler still sets `triage` without running the flow. A proper fix would be to route it through `case_status_transition_flow_dispatcher`, as the other Slack handlers do. I left it alone since you asked for the job-side fallback.
- `case_stable_reminder` still skips cases with no `stable_at` rather than counting from `created_at`. You only asked about the close reminder, so I didn't change it.

Nothing is committed.

----- next turn -----

Five commits since 2025-05-22 changed the snooze or dedup decision or its windows. The biggest one is `917a0b7b`, which silently changed the units of per-filter dedup windows.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29, "don't dedup on canary signals"): canary signals are never deduplicated, and canary rows are excluded from dedup matches. Both the default and the filter-based dedup paths are affected. No window change.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable"): the default window for signals with no dedup filter was hard-coded to 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45, so the window is now 45 minutes (2700 s) unless the env var is set.

3. **`d2675cf4`** (2025-07-03, "mask sensitive raw fields before processing"): not a change to snooze or dedup code. It redacts `password, secret, api_key, session_token, authorization` from `raw` before entity extraction (`SIGNAL_REDACTED_RAW_FIELDS`). Because filter expressions match on entities, this can change which instances match, so I list it as an indirect effect.

4. **`086dc910`** (2025-08-07, "simplify snooze filter checks"): two behaviour changes in `filter_snooze`.
   - An expired snooze filter used to be skipped with `continue`. It now hits `break`, which stops checking any later snooze filters on that signal.
   - The warnings for filters with no mode or no action were removed, and those filters are now skipped silently.
   - Snooze has no time window; it depends on the `expiration` datetime, which this commit did not change.

5. **`917a0b7b`** (2025-08-14, "share the lookback window computation"): per-filter dedup windows changed from minutes to seconds.
   - Before: `timedelta(minutes=f.window)`.
   - Now: `_window_start(f.window)`, which subtracts `f.window` seconds.
   - The model has always documented `SignalFilter.window` as seconds (`models.py:206`, default `60*60`), and the API schema default is 600. The UI labels the field "Window (minutes)" and offers 5, 10, 15, 20, 30, sending that number as-is. So any filter created in the UI with a 5–30 window now dedups over 5–30 seconds, where it used to be 5–30 minutes. Existing rows were not migrated, and I found no migration in this period.

**Windows as the code applies them today**

- **Default dedup (no dedup filters on the signal):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes. Dedup matches signal instances with a case that were created in the last 45 minutes.
- **Per-filter dedup:** `SignalFilter.window`, in seconds. Default 3600 (1 hour) on the model; 600 (10 minutes) in the API schema default.
- **Snooze:** no lookback window. Snoozed until `expiration`.

I haven't changed any code.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the per-filter dedup window from minutes to seconds. The UI sends minutes, so a window of 30 became 30 seconds, and two instances ten minutes apart were never grouped. I fixed the code so a filter's window is read as minutes again, which is what the UI says, and no stored data changed.

**Changes:**
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`.
- `src/dispatch/signal/models.py`: the comment on `SignalFilter.window` now says minutes. I also changed the column default from `60 * 60` to `60`, so it matches the comment's "1 hour".
- `tests/signal/test_signal_service.py`: two regression tests.
  - A window of 30 groups an instance created 10 minutes earlier. This is the reported case, and it fails with the seconds behaviour.
  - An instance created 40 minutes earlier, with a window of 30, is not grouped. This checks the window still applies.

**Tests:**
- `python -m pytest tests/signal`: 34 passed, 1 skipped.
- With the bug put back, the reported-case test fails and the other passes.
- Full `python -m pytest`: 367 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail on a clean checkout of HEAD, so they predate this change. My check used a separate worktree that may have imported the working-tree package, so treat that as strong evidence rather than proof. I did not investigate those failures.

**Decisions for you:**
- The API schema still defaults `window` to 600 (`src/dispatch/signal/models.py`, `SignalFilterBase`). Under minutes, a filter created through the API without a window now means 10 hours. That default predates this change and I left it alone. It's worth deciding whether it should be 60.
- Any filter created through the API with a seconds value during 2025-08-14 to now is now read as minutes, so it may be much longer than intended. I found no way to tell those apart from the stored data.

Commits: nothing is committed. The working tree also still has the earlier `triage_at` fallback in `scheduled.py`.

----- next turn -----

The cause is `086dc910` ("simplify snooze filter checks", 2025-08-07). It changed the expired-filter branch of `filter_snooze` from `continue` to `break`. If an expired snooze filter comes before a valid one on the same signal, the loop stops at the expired filter and never checks the valid one. That is why new "Okta: Impossible travel" instances for that user are not snoozed.

**Fix** (`src/dispatch/signal/service.py:763`): the expired branch uses `continue` again, so the loop moves on to the next filter.

**Regression test** (`tests/signal/test_signal_service.py`, `test_filter_actions_snooze_expired_filter_does_not_stop_later_snooze`): it has an expired snooze filter first, then a valid one for the same entity, and asserts the instance is snoozed. With `break` put back, the test fails. With the fix, it passes.

**Tests:**
- `python -m pytest tests/signal`: 35 passed, 1 skipped.
- Full `python -m pytest`: 368 passed, 8 failed, 4 skipped. The 8 failures are the same ones as before, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail on a clean HEAD checkout too, so they predate these changes.

Nothing is committed. The working tree also has the earlier changes to `scheduled.py` (the Monday check and the `triage_at` fallback), the minutes fix in `signal/service.py` and `signal/models.py`, and the new test files.

----- next turn -----

**Weekly Monday reminders (case close and stable)**
- The weekday check used `isoweekday()`, which returns 1 for Monday, and compared it with `calendar.MONDAY`, which is 0. Monday never matched, so no weekly reminders went out from the Monday 2025-08-18 run. Introduced by `c509d45e`, shipped in `main-81d8ae42` on 2025-08-13. The 2025-08-11 run still sent reminders.
- Fixed to `date.today().weekday() == calendar.MONDAY`. Regression test: `tests/case/test_case_scheduled.py`.
- The deploy link is inferred from the tag and commit order. I did not check the image contents.

**Evening TypeError in the close reminder job**
- `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is `None` for cases reopened straight into triage from the Slack reopen button (`reopen_button_click`), which skips the flow that stamps it.
- The job now counts from `triage_at`, falling back to `created_at`. Regression tests: `tests/case/test_case_scheduled.py`.
- Not confirmed: the logs have no case IDs, so I matched the error to this code path rather than to specific cases.
- Open: the reopen handler still bypasses the transition flow. The stable reminder still skips cases with no `stable_at`.

**Signal deduplication and snoozing (same batch of changes)**
- Per-filter dedup windows: `917a0b7b` changed the unit from minutes to seconds, so a window of 30 (set in the UI as minutes) became 30 seconds. Fixed to read the window as minutes again, with the model comment and default updated. Regression tests: `tests/signal/test_signal_service.py`.
- Canary signals: `a348bbd2` stopped canary signals from being deduplicated. No change needed.
- Snoozing: `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze after an expired one was never applied. Fixed back to `continue`. Regression test: `tests/signal/test_signal_service.py`.
- Full suite: 368 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai`, `tests/database`, and `tests/entity`, and also fail on a clean HEAD checkout. I did not investigate them.
- Open: the API schema still defaults `window` to 600, which now means 10 hours. Decide whether that should be 60.

**Status**
- Nothing is committed. The working tree has the changes in `src/dispatch/case/scheduled.py`, `src/dispatch/signal/models.py`, `src/dispatch/signal/service.py`, and `tests/signal/test_signal_service.py`, plus the new `tests/case/test_case_scheduled.py`.

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