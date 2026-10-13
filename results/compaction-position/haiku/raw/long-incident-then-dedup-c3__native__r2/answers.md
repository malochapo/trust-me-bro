**Root cause:** the Monday check in `src/dispatch/case/scheduled.py` can never be true. Commit `c509d45e` replaced the working check `date.today().isoweekday() == 1` with a helper that compares against `calendar.MONDAY`. In Python, `calendar.MONDAY` is `0`, while `isoweekday()` returns `1` for Monday. So `_is_reminder_day()` is always `False`, and both weekly reminders are silently skipped. The daily triage reminder (`case_triage_reminder`) doesn't use this helper, which is why it still arrives.

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # 1 == 0 -> always False
```

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on 2025-08-13 at about 16:40 UTC. The scheduler started at 16:40:06 and the web container at 16:40:07. Commit `81d8ae42` (`fix(case): exclude resolved_by in update (#6183)`) contains `c509d45e` (`refactor(case): share the weekly reminder check`, Jordan Lee, 2025-08-12). No other image was started between the commit and that deploy.

**Evidence from the logs:**
- Monday 2025-08-11 (before the deploy) sent weekly "Case close reminder" messages, including to several assignees.
- Monday 2025-08-18 (after the deploy) has no weekly close or stable reminder sends and no errors from the stable reminder. That matches the check returning `False` silently. Aug 18 is the first Monday after the deploy.
- The triage reminder still sent on Aug 18 and Aug 19–20, as the user reported.

**Separate issues I noticed (not the cause):**
- The stable reminder crashed daily from Jul 28 to Aug 12 on `case.stable_at is None`. Commit `32fa810f` (Aug 11) added an `if case.stable_at:` guard. That guard is in the deployed build, and the crash stops after Aug 12. The crash was fixed before the Monday regression started.
- `case_close_reminder` logs a `datetime - NoneType` error on `case.triage_at` for some cases on Aug 18 and Aug 20. It's caught per case, so it doesn't stop the other cases. It's worth a separate fix.

**Suggested fix (not applied, per your instruction):** compare against the 0-based weekday, for example `date.today().weekday() == calendar.MONDAY`, or drop `calendar` and use `isoweekday() == 1`. Add a test that pins `_is_reminder_day()` to a known Monday. I haven't checked whether the existing tests cover this helper.

----- next turn -----

The Monday check is fixed, and a regression test covers it. I did not commit anything.

**The fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches. The old code compared the 1-based `isoweekday()` against `calendar.MONDAY` (0), which is never true.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `date` in the scheduled module and checks that `_is_reminder_day()` returns True on Monday 2025-08-18 and False on the other six days of that week.

**Verification:**
- `python -m pytest tests/case/test_case_scheduled.py`: 7 passed.
- With the old check restored, the Monday case fails, so the test would have caught the bug.
- `python -m pytest tests/case`: 22 passed.

I only tested the helper, not the full reminder path. The weekly sends are still untested end to end. If you want that, the next step is a test that runs `case_close_reminder` and `case_stable_reminder` on a Monday and asserts that the reminders are sent.

----- next turn -----

The close reminder now falls back to `created_at` when `triage_at` is missing, and a regression test covers it. I haven't committed anything.

**Cause:** `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), and only when a case transitions into triage. Some triage cases have no `triage_at`, so `datetime.utcnow() - case.triage_at` raises `TypeError` for them. The subtraction runs before the Monday check, so the error appears every evening. The log shows 8 such errors, one per evening from Aug 13 to Aug 20. The per-case `try` catches each error, so the other cases still run, but the affected cases never get a reminder. I did not confirm which code path leaves `triage_at` empty, so that is still open.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`):
```python
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

**Test** (`tests/case/test_case_scheduled.py`): a parametrized test runs the real job against the test database with the Monday check patched to true. It covers four cases:
- no `triage_at`, created 8 days ago: reminder sent
- no `triage_at`, created 1 day ago: not sent
- `triage_at` 8 days old, created 30 days ago: sent (the existing `triage_at` path is still used)
- `triage_at` 1 day old, created 30 days ago: not sent

Against the original code, the no-`triage_at` case fails with no reminder sent. The test finds the job through `scheduler.registered_tasks`, because `scheduler.add` returns `None`.

**Results:**
- `tests/case/test_case_scheduled.py`: 11 passed.
- All tests matching `case`: 83 passed, 2 failed. Both failures also occur on the untouched code: `tests/ai/test_ai_service.py::TestGenerateReadInSummary::test_generate_read_in_summary_success_case` and `tests/database/test_service.py::test_restricted_case_filter_with_test_data`. I did not look into them.

**Decision for you:** the stable reminder has the same gap, but it skips cases with no `stable_at` without logging anything. I did not change it because you asked only about the close reminder. If you want the same `created_at` fallback there, I can apply it, but a stable case would then count from creation rather than from when it became stable. Also, should someone look into how cases end up in triage with no `triage_at`? The fallback fixes the symptom, not that path.

----- next turn -----



----- next turn -----

Since 2025-05-22, five commits changed the snooze or dedup logic in `src/dispatch/signal/service.py`. Two of them changed the time windows. Nothing was changed in the repo for this answer.

**Current windows, as the code applies them**

- **Default dedup (signal has no dedup filter):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes (`src/dispatch/config.py:95`). The code multiplies by 60 and treats the result as seconds, so the effective window is 2700 seconds.
- **Per-filter dedup window:** `SignalFilter.window` is an integer in seconds. The column default is 3600 (1 hour) in `src/dispatch/signal/models.py:206`. The API schema default is 600 (`models.py:282`). The code applies the value as seconds.
- **Snooze:** no time window. A snooze filter applies until its `expiration` datetime passes.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29, Will Sheldon), *fix(signal): don't dedup on canary signals (#6026)*. Canary signals are skipped for dedup and are excluded from the candidate instances in both dedup paths. No window change. At this point the default window was hard-coded to 1 hour.
2. **`7a9fe810`** (2025-06-19, Jordan Lee), *make the default deduplication window configurable*. The hard-coded 1 hour became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
3. **`5e136d7b`** (2025-07-03, Alicia Matsumoto), *add entity and trigger views to signal instance page (#6105)*. The part of the diff I read only added a `signals` field to `SignalFilterRead` in `models.py`. Its message says "refactor snooze filtering", but I did not check the rest of the commit, so I can't rule out a snooze change in it.
4. **`086dc910`** (2025-08-07, Sam Ortega), *refactor(signal): simplify snooze filter checks*. The mode and action checks were merged into one condition. The warnings for a missing mode or action were removed. Behavior change: an expired snooze filter now `break`s out of the loop instead of `continue`-ing. Any snooze filter after it on the same signal is no longer checked.
5. **`917a0b7b`** (2025-08-14, Jordan Lee), *refactor(signal): share the lookback window computation*. Added a `_window_start(seconds)` helper. The per-filter window changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which means seconds. This is a 60× shrink for every existing per-filter dedup window. The default dedup window is unchanged at 45 minutes.

**Things to check**

- Commit 917a0b7b is labeled a refactor but changes behavior. The UI in `SignalFilterCreateDialog.vue:196` offers window values 5, 10, 15, 20 and 30. I saw no conversion in the dialog or `store.js`, so those values are now sent as seconds. A filter a user set to 30 minutes is now a 30-second window. I did not confirm the submit path end to end.
- The window unit has changed before. `9c523348` (2023-04-07) moved it from seconds to minutes, and 917a0b7b moved it back to seconds. The model comment says seconds.
- The `filter_signal` docstring still says the default dedup window is 1 hour. It is 45 minutes now.

----- next turn -----

**Cause: `917a0b7b`** (2025-08-14, *refactor(signal): share the lookback window computation*). It changed the per-filter window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. The UI labels that field "Window (minutes)", so a window of 30 became 30 seconds. The two instances ten minutes apart fall outside a 30-second window, so they didn't group. The other commits I listed don't affect the window.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. Both the per-filter window and the default dedup window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which is no longer multiplied by 60) use it. The comment now says the window is in minutes.
- `src/dispatch/signal/models.py`: the column comment says minutes, and the column default is now 60 (one hour) instead of 3600.

Existing filters need no edits. Their stored values are the numbers the UI saved, so they go back to meaning minutes. No migration is needed.

**Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It is parametrized:
- instances 10 minutes apart with a window of 30 → deduplicated
- instances 40 minutes apart with a window of 30 → not deduplicated

With the seconds behavior restored, the 10-minute case fails; with the fix, both cases pass.

**Results:** `python -m pytest tests/signal tests/case` gives 60 passed and 1 skipped.

**Decisions for you**
- The API schema default for `window` is still 600 (`models.py:282`). Under minutes that means 10 hours. I didn't change it because it affects new API-created filters that omit a window. Should it be 60 to match the column default?
- Rows created without an explicit window before this change have 3600 stored, which now means 60 hours. That matches the behavior before 2025-08-14, but you may want to check those rows.
- Nothing is committed.

----- next turn -----

**Cause: `086dc910`** (2025-08-07, *refactor(signal): simplify snooze filter checks*). In `filter_snooze`, an expired snooze filter used to `continue` to the next filter. That commit changed it to `break`, so the loop stopped at the first expired filter and never checked the filters after it. For "Okta: Impossible travel", the expired filter came first, so the valid one was never evaluated and new instances were not snoozed.

**Fix:** `src/dispatch/signal/service.py` (around line 763): `break` back to `continue`. The other changes from that commit stay as they were.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It attaches an expired snooze filter first and a valid one (expiring in 30 days) second, both matching the same entity, and asserts the instance is snoozed. It fails with `break` and passes with `continue`.

**Results:** `python -m pytest tests/signal tests/case` gives 61 passed and 1 skipped.

Nothing is committed. The test file also changed on disk after my last edit. The diff stat matches my own additions, so I left it as is.

----- next turn -----

**Weekly reminders (Monday close and stable reminders)**

Assignees stopped getting the Monday reminders after the 2025-08-13 deploy. The weekday check compared Python's 1-based `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced this. I changed the check to `.weekday()` and added `tests/case/test_case_scheduled.py`, which fails on the old code. The first missed Monday was 2025-08-18.

Separately, `case_close_reminder` raised a TypeError every evening. `triage_at` is set only when a case transitions into triage, so some triage cases have it empty, and the job subtracted it from the current time. The error fired before the Monday check. The job now counts from `created_at` when `triage_at` is missing. The new test covers this case and the existing `triage_at` path. The exact code path that leaves `triage_at` empty is still unconfirmed. The stable reminder skips cases with no `stable_at` and I did not change that.

**Signal deduplication and snoozing**

- **Dedup windows (30 reported as 30 seconds):** `917a0b7b` changed the per-filter window to seconds, but the UI labels the field "Window (minutes)". I restored minutes in `src/dispatch/signal/service.py` and changed the column default in `models.py` to 60. Existing filters work without edits. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozes (expired filter blocks valid one):** `086dc910` changed an expired snooze filter from `continue` to `break`, so later filters on the same signal were never checked. I changed it back. Regression test: `test_filter_actions_snooze_skips_expired_filter`.
- **Canary signals:** `a348bbd2` (2025-05-29) excluded canary signals from dedup. I did not change this.

Test results: `python -m pytest tests/signal tests/case` gives 61 passed and 1 skipped. Two unrelated tests in `tests/ai` and `tests/database` already fail on the untouched code.

Nothing is committed. Open items: the schema default for `window` in `models.py` (600) is still a number of minutes, which is now 10 hours. Rows created before the change without an explicit window have 3600 stored, which now means 60 hours. Both need a decision.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
SNOOZE_BUG: 086dc910c308c8e5a91f5be8b4624cce11feae85
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES