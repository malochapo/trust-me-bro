**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") made the Monday check always false. The weekly reminders can't fire at all, so the assignee reminders stopped. The daily triage reminder doesn't use this check, so it still runs.

**The bug:** the old code compared against the literal `1`:

```python
if q >= 1 and date.today().isoweekday() == 1:
```

The refactor moved that comparison into a helper and used `calendar.MONDAY`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, because Python's `calendar` numbers Monday as 0. `isoweekday()` numbers Monday as 1 and Sunday as 7. So `_is_reminder_day()` never returns true. I confirmed both values in the sandbox: `calendar.MONDAY` is `0`, and `isoweekday()` on 2025-08-18 is `1`.

The helper is used in two places in `src/dispatch/case/scheduled.py`, so both weekly reminders are affected:
- `case_close_reminder` (triaging cases), line 49
- `case_stable_reminder` (stable cases), line 95

**Logs agree:**
- "Case close reminder sent to …" lines appear on Monday 2025-08-04 and Monday 2025-08-11.
- There are no send lines on Monday 2025-08-18 or later. The job still runs daily and still logs its timing, so it is running but never sending.

**The deploy:** `c509d45e` is an ancestor of `81d8ae42`. The scheduler pod restarted at **2025-08-13T16:40Z** (09:40 PT) with image `registry.example.com/dispatch:main-81d8ae42`. That is the first run with the bug, and the 2025-08-11 Monday sends came from the earlier image, `main-b05613b5`. I can't see a deploy record in the repo, so the image tag in the scheduler log is the evidence for the deploy. Someone should confirm it against the deploy pipeline.

**Fix (not applied):** compare against `1`, or against `calendar.MONDAY + 1`. The cleanest version is `isoweekday() == 1`, or `date.today().weekday() == calendar.MONDAY`, which uses the same 0-based numbering as `calendar`. The helper's existing name and docstring are fine. A regression test should check that the helper returns true on a Monday.

**Unrelated, noticed while reading the logs:** `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` for some triage cases where `triage_at` is null. This happens before and after the deploy. The per-case `try/except` catches it, so it doesn't block other cases, but it's worth a separate look.

I haven't changed any code.

----- next turn -----

The reminder check now fires on Mondays again, and a regression test covers it.

**The fix** (`src/dispatch/case/scheduled.py`, line 33): `_is_reminder_day()` compared `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It now uses `date.today().weekday()`, which uses the same 0-based numbering as `calendar`. This covers both the close and stable weekly reminders, since both call the helper.

**The regression test** (`tests/case/test_case_scheduled.py`): it pins the date with a patched `date` and checks one Monday (2025-08-11, expects `True`) and the six other days of that week (expects `False`). I ran it against the broken line and it fails on the Monday case, so it would have caught this.

**Results:**
- `python -m pytest tests/case/test_case_scheduled.py`: 7 passed.
- `python -m pytest tests/case`: 22 passed, against the local PostgreSQL.

The test covers the helper only, not the full scheduled job that sends the reminders. I didn't add a test for the job itself, because it needs database fixtures and the project decorators.

Nothing is committed. The diff is one line in the source file plus the new test file.

----- next turn -----

The TypeError is fixed, and cases with no `triage_at` now count their weekly reminder from `created_at`. The case test suite passes against PostgreSQL: 25 tests, including 3 new ones for the close reminder.

**What causes it:** `case_close_reminder` subtracts `case.triage_at` from the current time for every case in triage. Some triaging cases have `triage_at` set to NULL, so the subtraction raises `TypeError` on each run. The per-case `try/except` catches it, so the other cases still get their reminders, but the affected cases never do.

**Where NULL comes from:** `triage_at` is only set in `case_triage_status_flow`, and some paths reach triage without calling it:
- The `Any -> Triage` branch of the status dispatcher (`src/dispatch/case/flows.py`, around line 766) logs a warning and sets nothing.
- The Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py`, around line 1427) sets `case.status = CaseStatus.triage` directly and skips the flow.

I haven't confirmed which path produced the rows in production. Doing that needs a query against the case table, which I don't have access to here.

**The fix** (`src/dispatch/case/scheduled.py`):
```python
# cases that were never recorded as triaging count from when they were created
triaged_at = case.triage_at or case.created_at
span = datetime.utcnow() - triaged_at
```

**The tests** (`tests/case/test_case_scheduled.py`): they call the undecorated job with stub cases and check three things:
- A case with `triage_at` 8 days ago gets a reminder.
- A case with no `triage_at` but `created_at` 8 days ago gets a reminder. This one fails without the fix.
- A case with no `triage_at` and `created_at` 3 days ago gets no reminder.

The scheduler decorator doesn't return the function, so the tests look it up by its task name in `scheduler.registered_tasks`.

**Things to know:**
- The stable reminder is not changed. It already skips cases without `stable_at` (since commit `32fa810f`), so those cases get no reminder rather than a fallback. Applying the same `created_at` fallback there would be a one-line change if you want it.
- The "Any -> Triage" branch and the reopen button still skip setting `triage_at`. This fix only handles the symptom in the reminder job.
- The `_is_reminder_day` fix from the previous turn is still uncommitted with the rest of the work.
- `ruff` and `black` aren't installed here, so I wrapped the long test lines by hand.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or dedup decisions. One of them, `917a0b7b`, silently changed the unit of per-filter dedup windows, so filters now look back 60 times less far than before.

**Windows as the code applies them today** (`src/dispatch/signal/service.py`):
- **Snooze:** no window. A snooze filter applies until its `expiration` datetime passes, and the comparison uses UTC now.
- **Default dedup** (signals with no filters): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default **45 minutes**, converted to **2700 seconds** by `_window_start`.
- **Per-filter dedup** (signals with filters): `SignalFilter.window`, in **seconds**. The model default is 3600 (1 hour), and the API schema default is 600 (10 minutes).

**Commits**

1. **`a348bbd2`** (2025-05-29, Will Sheldon): *fix(signal): don't dedup on canary signals.* Canary signal instances are skipped in both dedup paths, so they neither dedup nor serve as the match for later instances. This is still in effect.

2. **`7a9fe810`** (2025-06-19, Jordan Lee): *make the default deduplication window configurable.* The default-path window was a hard-coded 1 hour and became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45. This shortened the default window from 60 to 45 minutes unless the env var is set.

3. **`086dc910`** (2025-08-07, Sam Ortega): *refactor(signal): simplify snooze filter checks.* This changed the behaviour of `filter_snooze` in two ways:
   - An expired snooze filter now ends the loop with `break` instead of `continue`, so later active snooze filters on the same signal are no longer checked.
   - Filters with no mode or no action are now skipped silently. The warning logs for them are gone.

4. **`917a0b7b`** (2025-08-14, Jordan Lee): *refactor(signal): share the lookback window computation.* This added `_window_start(seconds)`, which both dedup paths use. It also changed the per-filter window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, so the value is now read as seconds. Stored windows written under the old minutes meaning now look back 60 times less far. I have not checked whether existing filter rows were written in minutes or seconds, so this needs a data check.

Two other commits in the same range touched signal code but do not change snooze or dedup decisions: `4474af25` only adds logging of the outcome, and `d2675cf4` masks raw fields before processing. I did not check whether the masking changes what the dedup expressions match.

Nothing has been changed in the repo. The only file touched is a read-only check of the test file and the scheduler.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, Jordan Lee, "share the lookback window computation"). Before it, `filter_dedup` read a filter's `window` as minutes. That commit changed it to seconds, so a window of 30 became 30 seconds. Two instances ten minutes apart fall outside a 30-second window, so each opened its own case.

**Why I'm sure it's minutes:** the UI dialog is labelled "Window (minutes)", offers 5 to 30, and posts the raw number with no conversion. Stored filters are therefore minutes, and the fix doesn't need any data changes.

**The fix**
- `src/dispatch/signal/service.py`: the per-filter window is now `_window_start(f.window * 60)`, so 30 means 30 minutes again. Existing filters work without being edited.
- `src/dispatch/signal/models.py`: the comment on the `window` column said seconds, and now says minutes.

**The regression test:** `test_filter_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a filter with `window=30`, puts the first instance's `created_at` ten minutes in the past with a case attached, and expects the second instance to be deduplicated into that case. It failed on the current code and passes with the fix.

**Results**
- `python -m pytest tests/signal` → 33 passed, 1 skipped.
- `python -m pytest` (full suite) → 8 failed, 370 passed, 4 skipped. The 8 failures are in `tests/ai`, `tests/database` and `tests/entity`. I stashed my source changes and re-ran the full suite: the same 8 tests fail without them, so they predate this work. I did not investigate them.

**Things I did not change**
- The model defaults still don't match the minutes meaning. The column default is 3600 (60 hours under minutes, when the comment said an hour), and the API schema default is 600 (10 hours). Changing them affects new filters created without a window, so I left them for you to decide.
- The other commits from my earlier list are not part of this bug. `7a9fe810` only changed the default path, and `086dc910` changed snooze behaviour, which I did not touch.
- Nothing is committed. The uncommitted changes are the `case/scheduled.py` fix from the earlier turn, plus this turn's `signal` files and tests.

----- next turn -----

The cause was commit `086dc910` (2025-08-07, Sam Ortega, "simplify snooze filter checks"). In `filter_snooze`, that commit changed the expired-filter branch from `continue` to `break`. For the Okta signal, the expired filter came first, so the loop stopped there and never reached the filter valid until next month. New instances for that user were therefore not snoozed.

**The fix** (`src/dispatch/signal/service.py`): the expired branch is back to `continue`, so an expired snooze filter is skipped and the next filter is checked.

**The regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It lists an expired snooze filter before an active one for the same entity, and expects the instance to be snoozed. It failed before the fix and passes after.

**Results:** `python -m pytest tests/signal` → 34 passed, 1 skipped. I did not re-run the full suite this time. Last time, the 8 failures in `tests/ai`, `tests/database` and `tests/entity` were already failing without any of my changes.

The `break` calls in `filter_snooze` after an active match and in `filter_dedup` after a match are intended, so I left them alone. Nothing is committed. The working tree still has the earlier `case/scheduled.py` fix, the minutes-window fix in `signal/service.py` and `signal/models.py`, and the tests for each.

----- next turn -----

**Weekly reminders (case close and stable)**

Monday reminders stopped after the deploy that shipped on 2025-08-13. `_is_reminder_day()` compared `calendar.MONDAY` (0) against `date.isoweekday()`, which returns 1 for Monday, so the check was never true. `c509d45e` introduced it on 2025-08-12. The fix uses `date.weekday()`, and a regression test covers Monday through Sunday. The stable reminder uses the same function, so it was affected too. The deploy identity comes from the scheduler log's image tag. I found no deploy record in the repo, so treat it as likely rather than confirmed.

**Evening TypeError (case close reminder)**

The job subtracts `case.triage_at` from the current time. Some triaging cases have no `triage_at`, so every run raised a TypeError for those cases. The per-case `try/except` kept the other cases going. Cases with no `triage_at` now count from `created_at`, and three tests cover this. The source of the NULLs is not confirmed. The likely paths are the "Any -> Triage" branch of the status dispatcher and the Slack reopen button, which set triage without calling the flow that records `triage_at`. Production data would be needed to confirm.

**Deduplication window (GuardDuty)**

`917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds. A 30-minute window became 30 seconds, so instances ten minutes apart opened separate cases. The UI labels the field "Window (minutes)", so the code now reads it as minutes again, and existing filters need no edits. A regression test covers this case.

**Snoozing (Okta)**

`086dc910` (2025-08-07) changed the expired-filter branch of `filter_snooze` from `continue` to `break`. An expired snooze listed first stopped the loop, so a valid snooze after it never applied. The branch is back to `continue`, and a regression test covers it.

**Canary signals**

`a348bbd2` (2025-05-29) stopped canary signals from being deduplicated, and from serving as the match for later instances.

**Default window**

Signals with no filter are grouped within 45 minutes. The value comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which was added in `7a9fe810`.

**State of the work:** nothing is committed. The working tree holds the case-reminder fix, the signal window and snooze fixes, and the tests for each. The signal suite passes (34 passed, 1 skipped). In the last full-suite run, 8 tests in `tests/ai`, `tests/database` and `tests/entity` failed, and they fail without my changes too. Open items: the model defaults for `window` (3600 and 600, while the UI offers 5 to 30 minutes) still need a decision. The stable reminder also skips cases with no `stable_at`, and I left that alone.

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