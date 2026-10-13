**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the inline Monday check with a helper that compares against the wrong constant:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (Monday = 0 in `calendar`), but `isoweekday()` returns `1` for Monday. The comparison is therefore always false, so `case_close_reminder` and `case_stable_reminder` never send. The old code compared against `1`, which is correct. I confirmed both values with Python.

The daily triage reminder doesn't call this helper, which is why it keeps working.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler pod `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40:06Z (the web pod started at 16:40:07Z). `c509d45e` is an ancestor of `81d8ae42`, and the previous image (`main-b05613b5`) didn't have it. The scheduler logs confirm the switch: the old pod `xdp7k6gs2q-w6cj7` ran through 2025-08-12, and the new pod ran from 08-13.

**Evidence from the logs:**
- Monday 2025-08-11 (old image): "Case close reminder sent" for several assignees, and stable reminders sent.
- Monday 2025-08-18 (new image): no "Case close reminder sent" or stable-reminder sends. Triage reminders were sent that day.
- The 2025-08-11 sends came from the pre-`c509d45e` code. The first Monday that would have exercised the new check was 08-18, and that's when the reminders stopped.

**Separate issue (not the cause, but worth a follow-up):** `case_close_reminder` still reads `case.triage_at` without a `None` guard. On every run, one or more cases with no `triage_at` raise `TypeError` at `scheduled.py:47`. The per-case `try/except` catches it, so other cases still get processed, but it logs an ERROR daily. `32fa810f` added a `stable_at` guard for the same class of problem but didn't cover `triage_at`.

**Suggested fix (not applied):** use `date.today().isoweekday() == 1`, or `date.today().weekday() == calendar.MONDAY`, which is consistent with the `calendar` constant. Add a unit test for `_is_reminder_day` on a known Monday, since the existing tests evidently don't cover it. Guard `triage_at` the same way `stable_at` was guarded.

I made no code changes.

----- next turn -----

The weekly reminder check is fixed and covered by a regression test. The changes are uncommitted.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now compares `date.today().weekday()` to `calendar.MONDAY`. Both are 0-based. The old code compared the 1-based `isoweekday()` to 0, so it was never true.

**Regression test** (`tests/case/test_case_scheduled.py`, new file):
- `test_is_reminder_day` checks Monday through Sunday of a fixed week. The fake `date` class pins `today()`, so the test doesn't depend on the real date.
- `test_is_reminder_day_uses_calendar_monday` asserts the check agrees with `weekday()` on a known Monday.

I confirmed the tests catch the bug: with `isoweekday()` restored, the Monday case and the `calendar.MONDAY` test fail. With the fix, all 8 pass.

**Test runs** (`python -m pytest`, against the local PostgreSQL):
- `tests/case` and `tests/case_cost`: 42 passed.
- I did not run the full suite.

**Not changed:** `case_close_reminder` still reads `case.triage_at` without a `None` guard, so cases with no `triage_at` log a `TypeError` every day. The per-case `try/except` keeps the other cases going. It's a separate bug with the same shape as the `stable_at` fix in `32fa810f`, so I left it for you to decide. I can add the guard and a test if you want.

----- next turn -----

The close reminder no longer crashes on cases without `triage_at`. It counts those cases from `created_at` and still sends the weekly reminder. The changes are uncommitted.

**What causes the TypeError:** `triage_at` is only written when a case transitions into triage through the flow in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Two paths can leave it empty:
- The Slack reopen button handler (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets `case.status = CaseStatus.triage` directly and never runs the flow.
- The `triage_at` column was added in the 2022-08 migration with no backfill, so older cases have it empty.

I couldn't confirm which rows are affected. I had no production database access, and the logs record only the traceback, not case IDs.

**Changes:**
- `src/dispatch/case/scheduled.py:47`: `span = datetime.utcnow() - (case.triage_at or case.created_at)`. This uses the same `created_at` the triage reminder already uses.
- `tests/case/test_case_scheduled.py`: three new tests for the close-reminder job:
  - a case with no `triage_at` created 8 days ago gets the reminder,
  - a case with no `triage_at` created 2 days ago does not,
  - a case with `triage_at` 2 days ago and `created_at` 30 days ago does not, so `triage_at` still takes precedence.

**Verification:** `python -m pytest tests/case tests/case_cost` gives 45 passed, including the 11 tests in the new module. With the fallback removed, the no-`triage_at` test fails with the same `TypeError` as the logs.

**Left alone:**
- The reopen handler still skips the transition flow. Routing it through the flow would also set `triage_at`, but it's a behaviour change, so I didn't make it.
- The stable reminder still skips cases with no `stable_at` instead of falling back to `created_at`. You asked for the fallback only on the close reminder. I can apply it to the stable reminder too if you want.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 change how a new signal instance is snoozed or deduplicated. Two of them change the time windows, and one of those looks like a regression. I haven't changed any code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. Canary instances are skipped as the incoming signal and are excluded as dedup candidates, on both the default and filter paths. No time window involved.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The default window was hard-coded at 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` with a default of **45 minutes**, converted to seconds. The commit message doesn't mention that the default changed from 60 to 45 minutes. The `filter_signal` docstring still says 1 hour.

3. **`d2675cf4`** (2025-07-03), *mask sensitive raw fields before processing*. `signal_instance_create_flow` now redacts `password`, `secret`, `api_key`, `session_token` and `authorization` from `raw` before entities are extracted. This doesn't change a window, but entity matching in snooze and dedup can now see different values for payloads containing those keys.

4. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. An expired snooze filter used to be skipped with `continue`. It now uses `break`, which stops the loop. Any active snooze filter later in the list is no longer checked for that instance. The mode and action checks were folded into one condition, and their warning logs were removed. This is a behaviour change that the commit message doesn't mention.

5. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. This is the window regression. The deduplication filter window used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats the value as seconds, and the commit adds a comment saying `SignalFilter.window` is stored in seconds.

**Window values as the code applies them today**

- **Snooze:** no time window. A snooze applies until its `expiration` datetime. Expired snoozes are ignored, subject to the `break` change in `086dc910`.
- **Default dedup (signals with no dedup filter):** 45 minutes (2700 seconds) by default, or whatever `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is set to. A match needs an earlier instance of the same signal, with a case attached, that isn't canary.
- **Filter dedup (`SignalFilter.window`):** the value is read as **seconds**. The Pydantic default is 600, so 10 seconds if no window is set. The model column default is 3600 seconds.

**The likely regression in `917a0b7b`**

The filter dialog in `src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue` is labelled "Window (minutes)" and offers 5, 10, 15, 20 and 30. It sends those numbers as-is. Before `917a0b7b`, the backend read them as minutes, which matches the UI. Now they are read as seconds, so a filter the user set to 5–30 minutes checks a lookback of 5–30 seconds. That is a 60× reduction for every existing filter. The column comment from 2022 (`7e0ffbe1e`) says seconds, so it's unclear which unit the stored data actually uses. I didn't check the stored rows or any migration.

Not verified: I didn't run the signal tests or query the database, so the effects above come from reading the diffs.

----- next turn -----

The cause was `917a0b7b` (2025-08-14, "share the lookback window computation"). It made the filter's window be read as seconds, so a window of 30 looked back 30 seconds. Two instances ten minutes apart fell outside that, so both opened cases. The commit's own comment claimed the value was stored in seconds, but the UI labels the field "Window (minutes)" and offers 5–30, so the stored values are minutes. That's why existing filters need no edit.

**Fix** (`src/dispatch/signal/service.py:845`): the filter path now reads the window as minutes again, `_window_start(f.window * 60)`. The comment now says minutes. The default-window path from `7a9fe810` was already correct and is unchanged.

**Regression test:** `test_filter_actions_deduplicate_window_is_minutes` in `tests/signal/test_signal_service.py`, parametrized:
- window 30, earlier instance 10 minutes old: deduplicated. This fails on the old code.
- window 5, same setup: not deduplicated. This passes on both versions and checks that the window still bounds the lookback.

**Results:** `python -m pytest tests/signal tests/case tests/case_cost` gives 79 passed, 1 skipped.

**Left alone, for you to decide:**
- The column comment in `src/dispatch/signal/models.py:207` still says seconds, and the Pydantic default `window: int | None = 600` (`models.py:282`) is now 600 minutes (10 hours). The column default of 3600 is likewise 60 hours. Before `917a0b7b`, the code already read these as minutes, so I didn't change the defaults, but the comments and defaults are misleading.
- `086dc910` (`break` on expired snoozes) and the redaction in `d2675cf4` are still in place. Neither affects windows, so I didn't touch them.

----- next turn -----

The cause is `086dc910` (2025-08-07, "simplify snooze filter checks"). It changed the expired-snooze `continue` to `break` in `filter_snooze`. Whenever an expired snooze came before an active one in the filter list, the loop stopped and the active snooze was never checked. That's why new instances for that user came through unsnoozed.

**Fix:** `src/dispatch/signal/service.py` (~line 763) now uses `continue` for expired snooze filters again, so the loop moves on to the next filter.

**Regression test:** `test_filter_actions_snooze_after_expired_snooze` in `tests/signal/test_signal_service.py`. It lists a snooze that expired seven days ago before one valid for thirty days, both matching the same entity, and expects the instance to be snoozed. With `break` restored the test fails, and with `continue` it passes.

**Results:** `python -m pytest tests/signal tests/case tests/case_cost` gives 80 passed, 1 skipped.

The `service.py` edit from the earlier window fix is still in the file, and the test run above includes it. The file changed on disk while I was working, but its current content is what I tested, so I left it as is.

----- next turn -----

**Weekly reminders (weekday bug):** Assignees stopped getting the Monday reminders to close long-running triage and stable cases. The check `_is_reminder_day` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. The bug came in with `c509d45e` (2025-08-12, "share the weekly reminder check") and first shipped in `main-81d8ae42`, which started on the scheduler at 2025-08-13T16:40Z. The first Monday with no reminders was 2025-08-18. The fix uses `.weekday()`, and `tests/case/test_case_scheduled.py` covers each day of the week and the `calendar.MONDAY` comparison.

**Close reminder TypeError:** The job logged a TypeError every evening because `case.triage_at` was NULL for some cases in triage, and the code subtracted it from the current time. Cases can end up with no `triage_at` in two ways: the 2022 column was added without a backfill, and the Slack reopen button sets the status without running the transition flow that records it. I couldn't confirm which production rows are affected. The fix counts from `created_at` when `triage_at` is missing, and three tests cover that case, the recent-case case, and the case where `triage_at` takes precedence.

**Signal deduplication and snoozing:** Three commits since 2025-05-22 are involved:
- `917a0b7b` read the deduplication filter window as seconds instead of minutes, so a 30-minute window looked back 30 seconds. Fixed in `filter_dedup`, with a regression test that fails on the old code.
- `086dc910` changed an expired snooze from `continue` to `break`, so an expired snooze listed before an active one stopped the check and let the active snooze be skipped. Fixed, with a regression test that fails with `break`.
- `a348bbd2` changed canary signals so they are excluded from deduplication. This was a deliberate behaviour change, not a bug, and I left it as is.

Nothing is committed. The working tree has changes in `src/dispatch/case/scheduled.py`, `src/dispatch/signal/service.py`, `tests/signal/test_signal_service.py` and the new `tests/case/test_case_scheduled.py`. Last run: `python -m pytest tests/signal tests/case tests/case_cost` gives 80 passed, 1 skipped.

Open items: the reopen button still skips the transition flow, the stable reminder still skips cases with no `stable_at`, and the `triage_at` backfill hasn't been run. The column comment and Pydantic default for `SignalFilter.window` also still describe seconds, though the code now uses minutes; I didn't change those.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b0d
SNOOZE_BUG: 086dc910c3
CANARY: a348bbd267
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES