The root cause is an off-by-one in the weekday check, introduced by a refactor and shipped to production in image `main-81d8ae42` on 2025-08-13. I haven't changed any code.

**Root cause**

`c509d45e` ("refactor(case): share the weekly reminder check", Aug 12) moved the Monday test into a helper in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

These two conventions disagree:
- `date.today().isoweekday()` is 1 for Monday (Monday=1 through Sunday=7).
- `calendar.MONDAY` is 0 (Python's `weekday()` convention, Monday=0).

I confirmed both values in the sandbox. So `_is_reminder_day()` is always `False`. The original code compared against the literal `1` and was correct, so the helper refactor is the regression.

Both long-running reminders go through this check: `case_close_reminder` (triage, line 49) and `case_stable_reminder` (stable, line 95). Only the Monday-gated sends are blocked. `case_triage_reminder` never calls the helper, which is why the daily triage reminders still arrive.

**Deploy that shipped it**

- `81d8ae42` ("fix(case): exclude resolved_by in update", #6183) contains the refactor `c509d45e` as an ancestor (verified with `git merge-base --is-ancestor`).
- The web pod started at 2025-08-13T16:40:07Z on `registry.example.com/dispatch:main-81d8ae42` (`api.log:13201`).
- The scheduler restarted on the same image at 2025-08-13T16:40:06Z (`scheduler.log:18851`).

**Confirmation in the logs**

- Monday 2025-08-18 at 18:00 is the first Monday after that deploy. `case_close_reminder` and `case_stable_reminder` both ran on the new scheduler pod (`scheduler-mhtsgqwwx-q5q2n`), and no reminder sends were logged.
- Monday 2025-08-11 ran on the old image `main-b05613b5` before the deploy, so the reminders would have fired then.

**Other things I checked**

- The `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors from 2025-07-28 onward come from `case.stable_at` being null. They are per-case, caught, and already fixed by `32fa810f` (2025-08-11). They do not explain the missing reminders.
- `case_close_reminder` still has the same null-timestamp problem for `triage_at`. The 2025-08-18 log shows an ERROR at `case/scheduled.py:55` for a case with null `triage_at`. It is caught per case, so it does not block the other cases, but it is a remaining bug the `32fa810f` fix did not cover.

**Suggested fix (not applied)**

Use the same convention as `isoweekday()`, e.g. `date.today().isoweekday() == 1`, or switch to `date.today().weekday() == calendar.MONDAY`. A small unit test that asserts `_is_reminder_day()` returns true on a Monday would have caught this in review.

----- next turn -----

The reminder check is fixed, and a regression test covers it. Nothing is committed.

**Fix:** `src/dispatch/case/scheduled.py:33` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use Python's Monday=0 convention, so the long-running reminders fire on Mondays again.

**Regression test:** `tests/case/test_case_scheduled.py` is new. It pins "today" to each day of one week and asserts that `_is_reminder_day()` is true only on Monday. I didn't add a time-mocking dependency, so it patches `date` in the scheduled module.

**Verification:**
- `python -m pytest tests/case/test_case_scheduled.py`: 7 passed.
- With the original `isoweekday()` line restored temporarily, the Monday case fails, so the test catches the bug. I then restored the fix.
- `python -m pytest tests/case`: 22 passed.

**Limits:**
- The test covers the helper only. It doesn't exercise `case_close_reminder` or `case_stable_reminder` end to end, because those run through the project-context decorator and need database setup.
- I didn't run the full suite.

**Not changed:** `case_close_reminder` still has no null guard for `triage_at`. Cases with a null `triage_at` raise an ERROR every day, as in the 2025-08-18 log. This is caught per case, so it doesn't block other cases. It's a separate fix, and I can do it if you want.

----- next turn -----

I fixed the job so cases with no `triage_at` count from `created_at`, and added tests. The root cause of the missing timestamps is not confirmed.

**What causes the TypeError**

`case_close_reminder` does `datetime.utcnow() - case.triage_at` for every case in triage status. Some of those cases have `triage_at = NULL`, so the subtraction raises `TypeError`. The per-case `except` catches it and logs it, so the other cases still run. That's the 40 TypeErrors in `scheduler.log`, one per affected case per evening.

The code paths that set triage status don't always set `triage_at`:
- The transition flow sets it (`case_triage_status_flow`), and the API update path goes through that dispatcher.
- The Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) assigns `case.status = CaseStatus.triage` directly and never runs the flow.

The reopen path only leaves `triage_at` null if the case was never triaged before it was closed, and the new→closed flow does set it. So the reopen button may not be the source. Cases that predate the flow are another possibility. Confirming which one it is needs a query against production for `status = 'Triage' AND triage_at IS NULL`, and I can't run that from here.

**Fix** (`src/dispatch/case/scheduled.py:42-44`)

```python
# cases without a triage timestamp count from when they were created
span = datetime.utcnow() - (case.triage_at or case.created_at)
```

**Tests** (`tests/case/test_case_scheduled.py`)

- `test_case_close_reminder_counts_from_created_at_when_not_triaged` runs the real job body against stub cases. It covers: no `triage_at` and created 8 days ago (sent), `triage_at` 8 days ago (sent), `triage_at` 2 days ago (not sent), and no `triage_at` and created 2 days ago (not sent).
- The job body is reached through the registered scheduler task, unwrapping its `timer` and `scheduled_project_task` layers.
- Without the fallback, the no-`triage_at` case fails with the same TypeError as the logs.

**Verification**
- `python -m pytest tests/case/test_case_scheduled.py`: 11 passed.
- `python -m pytest tests/case`: 26 passed.

**Also noticed:** `src/dispatch/scheduler.py:43` returns `decorator`, so `scheduler.add(...)` gives the decorator back rather than the function. As a result, the module-level names like `case_close_reminder` are `None` after decoration. The registered job still works, so I left it alone. The tests reach the job through `scheduler.registered_tasks` for that reason.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or deduplication logic in `src/dispatch/signal/service.py`. Only one of them changed a time window's value. The `src/dispatch/` files that mention snooze or dedup were searched, and the signal, config, and model files were checked against the log since that date. I made no code changes.

**Commits, oldest first**

1. **`a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals"**
   - `filter_dedup` returns early for canary signals. Canary instances are also excluded from both dedup lookups.
   - No window change.

2. **`7a9fe810`, 2025-06-19, "make the default deduplication window configurable"**
   - Adds `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default **45 minutes**.
   - This window applies to signals with no dedup filter. It was hard-coded at **1 hour** before, so the effective default dropped from 60 to 45 minutes.

3. **`086dc910`, 2025-08-07, "refactor(signal): simplify snooze filter checks"**
   - Snooze checks are merged into one condition. The "no mode" and "no action" warnings are removed.
   - An expired snooze filter now hits `break` where it used to hit `continue`. The loop stops, so any later active snooze filter on the same signal is never evaluated.
   - No window value is involved. The snooze window is the filter's `expiration` timestamp.

4. **`917a0b7b`, 2025-08-14, "refactor(signal): share the lookback window computation"**
   - Adds `_window_start(seconds)`.
   - Per-filter dedup windows change unit. The old code was `timedelta(minutes=f.window)`. The new code is `_window_start(f.window)`, which treats `f.window` as **seconds**. So a filter with `window = 600` now looks back **10 minutes**, not 10 hours.
   - The model already documented seconds (`src/dispatch/signal/models.py:206-208`, default `60 * 60`). The API schema default is `600` (`models.py:282`, from `5940842ad`, 2025-05-07), which the old code read as 10 hours.

**Windows as the code applies them today**

- Signal with no dedup filter: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` × 60 seconds. Default **45 minutes**.
- Dedup filter: `f.window` in **seconds**. Model default 3600 (**1 hour**). API default 600 (**10 minutes**).
- Snooze filter: no lookback. It lasts until `expiration`.

**Things to check**

- `docs/docs/administration/settings/signal/filter.mdx:35` says the default dedup window is one hour. The code's default is 45 minutes.
- Any dedup filters created under the old minutes interpretation now match 60 times less history. Those filters are not migrated.
- The `break` in `086dc910` means an expired snooze can hide a later active one. I haven't checked whether that's intended.

----- next turn -----

The full-suite baseline run is still going in the background. Its completion will bring me back to restore the stash and compare failures. I'll hold off on any further changes until then.

----- next turn -----

I'm waiting for the baseline test run to finish. My tracked changes are temporarily in `stash@{0}`, and the monitor will report once they're popped back. I'll compare the failure lists after that and report the results.

----- next turn -----

The commit that caused it is `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed how a deduplication filter's window was read, from minutes to seconds. The UI labels the field "Window (minutes)" and offers 5–30, so a window of 30 now looks back 30 seconds instead of 30 minutes. Your two instances ten minutes apart fall outside that and open two cases.

**Fix** (`src/dispatch/signal/service.py:845-846`)
- `window = _window_start(f.window * 60)`, so the stored value is read as minutes, as the UI intends.
- Existing filters need no edits, because the UI has always written minutes.
- In `src/dispatch/signal/models.py:208` I corrected the comment to say minutes. I didn't change the stored defaults.

**Regression test** (`tests/signal/test_signal_service.py::test_filter_window_is_in_minutes`)
- The first instance is ten minutes old, the filter window is 30, and the second instance should deduplicate onto the first case.
- It passes with the fix and fails with the old line restored.

**Test results**
- `python -m pytest tests/signal tests/case`: 59 passed, 1 skipped.
- Full suite: 8 failures, all in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail on the original code, so they predate these changes. I did not investigate them.

**Things to check**
- The model defaults are still `60 * 60` (`models.py:207`) and the API default is `600` (`models.py:282`). Under the minutes meaning, a filter created without an explicit window gets 60 hours or 10 hours. This was also true before `917a0b7b`. Changing it needs a migration, so I left it. Tell me if you want that handled.
- The docs at `docs/docs/administration/settings/signal/filter.mdx:35` still say one hour for the default, and the code's default is 45 minutes.

Nothing is committed. The changes are in `signal/service.py`, `signal/models.py`, `tests/signal/test_signal_service.py`, plus the earlier untracked `tests/case/test_case_scheduled.py` and the `case/scheduled.py` edit from before.

----- next turn -----

The cause is `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). It changed the handling of an expired snooze filter from `continue` to `break`. `filter_snooze` walks the signal's filters in order, so the expired filter ended the loop before the valid one was checked. Every new instance for that user then fell through to dedup and was not snoozed.

**Fix** (`src/dispatch/signal/service.py`, expired-filter check in `filter_snooze`)
- Changed `break` back to `continue`.

**Regression test** (`tests/signal/test_signal_service.py::test_filter_actions_snooze_expired_then_active`)
- Two snooze filters match the same entity: one expired 7 days ago and listed first, one valid for 30 more days.
- It asserts that `filter_signal` returns True and the instance's action is `snooze`.
- With `break` restored, it fails. With `continue`, it passes.

**Tests**
- `python -m pytest tests/signal tests/case`: 60 passed, 1 skipped.

The working tree also still has the earlier changes: the window fix in `signal/service.py` and `signal/models.py`, the `case/scheduled.py` fix, and the test files. Nothing is committed.

I did not check the production filter rows for "Okta: Impossible travel". The diagnosis comes from the code and the commit history.

----- next turn -----

Here is the recap for the weekly report.

**Monday reminders (case close and stable)**
- The weekday check compared `isoweekday()`, where Monday is 1, with `calendar.MONDAY`, where Monday is 0. Monday reminders never went out.
- The check was introduced in `c509d45e` (2025-08-12) and deployed in image `main-81d8ae42` on 2025-08-13. Monday 2025-08-11 ran on the previous image, so 2025-08-18 is the first missed Monday.
- Fix: `date.today().weekday() == calendar.MONDAY` in `_is_reminder_day()`, with a regression test in `tests/case/test_case_scheduled.py`.

**Evening TypeError (case close reminder)**
- Cases in triage with no `triage_at` raised `TypeError` on the subtraction, so each one was logged and skipped every evening.
- Fix: count from `created_at` when `triage_at` is missing, with job-level tests.
- Not confirmed: how these cases got a null `triage_at`. The Slack reopen button bypasses the status flow that sets it, but I could not tie the logged cases to it, and the affected records have not been identified.

**Signal filters (same batch of changes)**
- Dedup windows: `917a0b7b` read a filter's window as seconds, but the UI labels it minutes. A window of 30 looked back 30 seconds. Fixed in `filter_dedup` with `f.window * 60`, with a regression test.
- Snoozing: `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze listed after it was never checked. Restored `continue`, with a regression test.
- Canary: `a348bbd2` (2025-05-29) stopped deduplicating canary signals.
- Default window for signals with no filter: 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

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

Nothing is committed. The working tree holds the fixes and tests for all three problems. The full suite has 8 failures in AI, database, and entity tests that also fail on the original code. I did not investigate them.