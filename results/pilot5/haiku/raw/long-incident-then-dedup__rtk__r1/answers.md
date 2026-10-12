**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the Monday check with a helper that compares against the wrong constant.

- Before, `case/scheduled.py` checked `date.today().isoweekday() == 1`, which is Monday, since `isoweekday()` is 1–7 with Monday = 1.
- The new helper `_is_reminder_day()` (`src/dispatch/case/scheduled.py:31-33`) returns `date.today().isoweekday() == calendar.MONDAY`. In Python, `calendar.MONDAY` is `0`, so the check is `isoweekday() == 0`, which is never true. I confirmed both values in the sandbox.
- The helper is used at `scheduled.py:49` (`case_close_reminder`, triage) and `scheduled.py:95` (`case_stable_reminder`, stable). So the weekly reminders for both case types never fire.
- The daily triage reminder (`case_triage_reminder`) doesn't go through this check, which is why it still arrives.
- The sibling check in `incident/scheduled.py:229` still uses `== 1` and isn't affected.

**The deploy:** the commit is dated 2025-08-12 14:05 -0700 (21:05Z). The first production rollout that includes it is at **2025-08-13T16:40Z**. At that point the scheduler pod switched from `scheduler-xdp7k6gs2q-w6cj7` to `scheduler-mhtsgqwwx-q5q2n`, and the web pods switched from `web-bsnvb5wc2t-7lt2t` to `web-5dkmr9s9s-xxktx`. The old pods run until 16:40:38Z and the new ones start at 16:40:06Z, so this is one rollout.

**Evidence from the logs:**
- Monday 2025-08-04 and Monday 2025-08-11 (both on the old pod, before the commit): case close reminders were sent to multiple assignees.
- Monday 2025-08-18 (new pod): triage reminders were sent, but no "Case close reminder sent" or stable-case reminder appears.
- Only the triage reminders show up on the new pod after the rollout.

Two other things I saw but did not look into:
- `32fa810f` ("fix(scheduler): not all cases have a stable_at date", 2025-08-11) is the fix for the `NoneType` error that appeared nightly in `case_stable_reminder` and `case_close_reminder`. It shipped in the same 08-13 rollout, but I didn't check whether the errors stopped. After the rollout the log still shows about one matching error per day, so it's worth a look.
- Some commits in the window (`3d3bf623`, 2025-08-13 11:47 -0700) landed after the rollout time, so they are not part of the rollout. I matched the rollout to commits by timestamp only, since the logs don't record a commit hash.

No code changed. The fix is to restore `isoweekday() == 1` in `_is_reminder_day()`, or to compare against `calendar.MONDAY + 1` if you want the constant. Tell me if you want that applied.

----- next turn -----

The Monday reminder check is fixed, and there's a regression test for it. One caveat: `python -m pytest` fails in this shell, so I ran the tests through `pytest.main` in the same interpreter instead.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches. The previous `isoweekday()` is 1-based and never equals `calendar.MONDAY` (0). I haven't committed.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `dispatch.case.scheduled.date` and checks `_is_reminder_day()` for a Monday and the six other days of one week. With the old line restored, the Monday case fails (`test_is_reminder_day[today0-True]`). With the fix, all 7 cases pass.

**Full suite:** 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail with my change stashed, so they predate it. I didn't investigate them.

**`python -m pytest` problem:** it fails at conftest import with `No module named 'slack_sdk'`, from any working directory. But `slack_sdk` imports fine in that interpreter, and `pytest.main` in the same interpreter runs the tests normally. I didn't find the cause. The venv on `PATH` also has no pip, so I couldn't reinstall dependencies there.

----- next turn -----

The close reminder no longer raises. Cases in triage with no `triage_at` now count from `created_at`, and they get their weekly reminder.

**Cause:** `triage_at` is set only by `case_triage_status_flow` (`src/dispatch/case/flows.py:594-596`). Some paths change a case to triage by assigning `case.status = CaseStatus.triage` directly and skip that flow. The Slack handlers in `plugins/dispatch_slack/case/interactive.py` do this at lines 1312, 1427 and 2246. Those cases keep `triage_at = NULL`, and `datetime.utcnow() - case.triage_at` raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The job's `try/except` logs it and moves on, so the case is skipped every night. The post-deploy log shows this error at `scheduled.py:47` each evening from 2025-08-14. The earlier `stable_at` fix only covered the stable job.

**Fix** (`src/dispatch/case/scheduled.py:47`): `span = datetime.utcnow() - (case.triage_at or case.created_at)`. I left the Slack paths as they are, since the fallback covers them.

**Test** (`tests/case/test_case_scheduled.py`, `test_case_close_reminder_without_triage_at_counts_from_created_at`): a case in triage with no `triage_at` and created 8 days ago gets a reminder. A case created 2 days ago in the same project does not. With the fix reverted, the test fails. With it in place, all 8 tests in the file pass.

**Full suite:** 367 passed, 4 skipped, 8 failed. The 8 are the same pre-existing failures as before (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`).

Things to know:
- I ran the tests with `python -c "import pytest; pytest.main(...)"`. `python -m pytest` still fails with the `slack_sdk` import error described last time.
- `case_stable_reminder` still skips a case with no `stable_at` without sending anything. You asked about the close job, so I left it alone. Say if you want the same fallback there.
- Nothing is committed.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed the snooze or dedup logic. Only the 2025-08-14 commit changes a window's unit, and it is the one to look at first.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*. Canary instances skip dedup, and canary instances are excluded when matching duplicates. Windows: none changed.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The default window, used only when a signal has no filters, moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95-97`). It defaults to 45 minutes, and the code converts it with `* 60` to seconds (`service.py:805`).

3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. An expired snooze filter used to `continue` to the next filter. It now `break`s (`service.py:762-763`), so a later active snooze filter on the same signal is no longer checked. The mode and action checks were also merged. No windows changed. Snooze has no window: it applies until the filter's `expiration`, and a snooze filter without an expiration is skipped.

4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. This is labelled a refactor, but it changed units. The old code computed `timedelta(minutes=f.window)` (`917a0b7b^:service.py:842`). The new `_window_start(f.window)` (`service.py:784-786`, `:846`) treats `f.window` as seconds. The default window is unchanged at 45 minutes.

**Window values as the code applies them today**
- Default dedup (no filters): 45 minutes, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- Filter dedup window: `SignalFilter.window` is read as **seconds**. The database column defaults to 3600 (1 hour) (`src/dispatch/signal/models.py:206-208`). The request schema defaults to 600 (`models.py:282`).

**Problem:** The UI still offers 5, 10, 15, 20, 30 under the label "Window (minutes)" (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:56, 196`). I found no conversion to seconds in the UI, so the value is sent as-is. Since `917a0b7b`, a 30-minute dedup window set in the UI becomes a 30-second window. I did not read the API handler that stores the value, so I have not confirmed that nothing converts it there.

I did not inspect `5e136d7b`, `d2675cf4`, `4474af25`, or the flow changes in `signal/flows.py`. They touch the same files, but I did not check whether they change the snooze or dedup decision. No code was changed.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed how `SignalFilter.window` is read, from minutes to seconds, without changing the UI or the stored values. A window of 30 now means 30 seconds, so two instances ten minutes apart never match. The other commits don't explain this. The `7a9fe810` default-window change only applies to signals with no filters.

**Fix**
- `src/dispatch/signal/service.py:845-846`: the window is read as minutes again: `_window_start(f.window * 60)`. Existing filters hold minutes already (the UI offers 5–30), so they work without edits.
- `src/dispatch/signal/models.py:206-208`: the column comment now says minutes. It said seconds, which was wrong.

**Regression test**
- `tests/signal/test_signal_service.py::test_filter_dedup_window_is_in_minutes`: a 30-minute dedup filter. An instance 10 minutes old is grouped into the earlier instance's case. One 40 minutes old is not.
- With the fix reverted, the 10-minute case fails. With the fix in place, both cases pass.
- I added `import pytest` at the top of that file.

**Results**
- Full suite: 369 passed, 4 skipped, 8 failed. The 8 failures are the same pre-existing ones as before (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`).
- `python -m pytest` still fails with `No module named 'slack_sdk'`, even though `slack_sdk` imports in the same interpreter. I ran the suite with `python -c "import sys,pytest; sys.exit(pytest.main([...]))"` as before. I did not find the cause.

**Decision for you**
- The column default is still `60 * 60`, which is now 3600 minutes (about 2.5 days) for a filter created without a window. That matches the behavior before 2025-08-14, so I left it. The old comment said 1 hour, so the intent may have been 60 minutes. Changing it would only affect new filters. Say if you want it changed.

Nothing is committed. The test file reported an on-disk change I didn't make, so I checked the suite against its current contents.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). It changed an expired snooze filter from `continue` to `break` in `filter_snooze` (`src/dispatch/signal/service.py:763`). The loop stops at the first expired filter, so a valid snooze filter later in the list is never checked. The Okta user's expired filter came first, so new instances were not snoozed.

**Fix:** `src/dispatch/signal/service.py:763` is back to `continue`, so an expired filter is skipped and the loop goes on to the next one.

**Regression test:** `tests/signal/test_signal_service.py::test_filter_actions_snooze_expired_filter_before_valid_filter`. It sets up an expired snooze filter first and a valid one second, both matching the same entity, and asserts the instance is snoozed. With `break` restored, the test fails. With `continue`, it passes.

**Results:** The full suite gives 370 passed, 4 skipped, 8 failed. The 8 failures are the same pre-existing ones as before. I ran it with the `python -c "import sys,pytest; sys.exit(pytest.main(...))"` workaround again, because `python -m pytest` still fails with the `slack_sdk` import error.

Two files changed on disk during this session: `service.py` and `test_signal_service.py`. I read the current contents and kept them. The only differences from my edits are the ones described above.

Nothing is committed.

----- next turn -----

**Weekly reminders and the evening TypeError (both in `src/dispatch/case/`)**

- **Missed Monday reminders:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so no weekly close or stable reminder went out on any day. Commit `c509d45e` (2025-08-12) introduced it. The image containing it is `main-81d8ae42` (started 2025-08-13 16:40Z), which includes `c509d45e`. The fix uses `date.today().weekday() == calendar.MONDAY`. The regression test covers Monday and Tuesday through Sunday.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Slack handlers in `plugins/dispatch_slack/case/interactive.py` set a case to triage by assigning `case.status` directly, which skips `case_triage_status_flow`, so `triage_at` stays NULL. The job now counts from `triage_at or created_at`. The regression test sets an 8-day-old case with no `triage_at` and expects a reminder, and a 2-day-old case in the same project and expects none.
- **Log caveat:** The TypeError appears in `scheduler.log` from 2025-07-28, before the 08-13 image started. The logs don't tie it to that deploy, and the cause is the missing field regardless.

**Signal bugs**

- **Dedup windows ignored the UI's minutes:** Commit `917a0b7b` (2025-08-14) treated `SignalFilter.window` as seconds, so a 30-minute window became 30 seconds. The fix reads it as minutes again and corrects the column comment. The regression test is `test_filter_dedup_window_is_in_minutes`.
- **Snoozes broken by an expired filter:** Commit `086dc910` (2025-08-07) changed an expired snooze filter from `continue` to `break`, so a valid snooze filter later in the list was never checked. The fix restores `continue`. The regression test is `test_filter_actions_snooze_expired_filter_before_valid_filter`.
- **Canary signals:** Commit `a348bbd2` (2025-05-29) makes canary instances skip dedup and excludes them from matches.
- **Default window:** Signals with no filters group instances within 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`, 2025-06-19; it was 1 hour before).

**State**

- Full suite: 370 passed, 4 skipped, 8 failed. The 8 failures predate today's work (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`).
- `python -m pytest` still fails on `slack_sdk`, so I ran tests with the `pytest.main` workaround.
- Nothing is committed. Open choice: the column default for a filter created without a window is 3600 minutes (about 2.5 days). I left it unchanged.

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