**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` can never return `True`. It compares `date.today().isoweekday()` to `calendar.MONDAY`, but those use different numbering. `isoweekday()` returns 1 for Monday, while `calendar.MONDAY` is 0 (I confirmed both in Python). So `q >= 1 and _is_reminder_day()` is always false in `case_close_reminder` and `case_stable_reminder`, and neither weekly reminder is sent. The daily `case_triage_reminder` doesn't call this check, so it still runs.

**The change:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It replaced the inline `date.today().isoweekday() == 1` with the helper, and that helper uses `calendar.MONDAY`. The old inline check was correct, so this was a refactor that changed behavior.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, which started on the scheduler at 2025-08-13 16:40:06 UTC (09:40 PDT). `81d8ae42` ("fix(case): exclude resolved_by in update", #6183) contains `c509d45e`. I'm inferring from the tag name that the image was built from that commit.

**Log evidence:**
- Monday 2025-08-04 and Monday 2025-08-11 both sent close reminders (`Case close reminder sent to …`), under image `main-b05613b5`.
- Monday 2025-08-18 sent none. The scheduler ran `main-81d8ae42` from 08-13 onward.
- Daily `Case triage reminder sent` lines continue through the gap.

**Other things I checked:**
- The `stable_at` `TypeError` that `32fa810f` fixed (#6179) is in the deployed image, and no stable-reminder errors appear after 08-13.
- `case_close_reminder` still logs a `TypeError` for `triage_at` being `None` every day. It's caught per case, so it doesn't stop the other reminders, and it predates the outage. I didn't treat it as the cause.

**Suggested fix (not applied):** use the 0-based weekday (`date.today().weekday() == calendar.MONDAY`), or compare against `1` as the old code did. A test that pins `_is_reminder_day` to a known Monday would catch this kind of mismatch. No code was changed.

----- next turn -----

The reminder bug is fixed and there's a regression test for it. The Monday check in `src/dispatch/case/scheduled.py` now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. The old `isoweekday()` is 1-based, so it never matched and neither weekly reminder was sent.

**Changes**
- `src/dispatch/case/scheduled.py:33`: `_is_reminder_day()` now returns `date.today().weekday() == calendar.MONDAY`.
- `tests/case/test_case_scheduled.py` (new): a parametrized test of `_is_reminder_day()` on a Monday (should be True), a Tuesday and a Sunday (should be False). It patches `date` in the scheduled module with a fixed-day stand-in, since the project has no time-freezing library.

**Verification**
- The new test passes with the fix. Against the original code, the Monday case fails, so it would have caught this.
- `python -m pytest tests/case` passes (18 tests).
- Full `python -m pytest`: 8 failed, 362 passed, 4 skipped. All 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They fail the same way on the base commit with my changes stashed, so they're pre-existing and unrelated to this fix.

**Not covered:** the test checks the helper, not the full `case_close_reminder` / `case_stable_reminder` jobs. Those need the scheduler decorators and a database fixture, so I kept the test narrow. I haven't committed anything.

----- next turn -----

The close reminder's `TypeError` is fixed: the job now counts from `created_at` when `triage_at` is missing. I added tests that exercise the job itself and confirmed they fail on the old code.

**Cause:** `case_close_reminder` subtracts `case.triage_at` from the current time, and `triage_at` is only set inside `case_triage_status_flow`. Cases that reach `triage` without that flow keep `triage_at = NULL`, so the subtraction raises. The API update path and the normal Slack triage path both run the flow. The one that doesn't is `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py` (around line 1427), which sets `case.status = CaseStatus.triage` directly. A case closed straight from `new` and then reopened therefore has no `triage_at`.

I couldn't confirm that from the data. The logs have no case IDs, so I can't see which case is failing. They do show exactly one close-reminder error per evening, which points to one stuck case rather than a systemic problem.

**Changes:**
- `src/dispatch/case/scheduled.py`: `span = datetime.utcnow() - (case.triage_at or case.created_at)`, with a short comment explaining why.
- `tests/case/test_case_scheduled.py`: three new tests, run against the real job through the scheduler registry:
  - no `triage_at`, created 8 days ago → reminder sent
  - no `triage_at`, created 2 days ago → no reminder
  - `triage_at` set → still counts from `triage_at`
- The factory's `Params` override any `status` passed in, so the tests set status and timestamps after creating the case.

**Verification:**
- `python -m pytest tests/case` passes (21 tests).
- Against the pre-fix code, the created-at test fails with the same `TypeError` from the logs.
- Full `python -m pytest`: 8 failed, 365 passed, 4 skipped. The 8 failures are the same pre-existing ones as before.

**Not changed:**
- I didn't touch `reopen_button_click`. Setting `triage_at` there, or routing it through the transition flow, would be a separate fix.
- The stable reminder isn't changed either. It already skips cases with no `stable_at`, which `32fa810f` added, so it doesn't raise. Your request was specific to the close-reminder job, so I left it.
- Nothing is committed.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 changed snooze or dedup decisions. Two of them quietly changed time windows, and the current code is the result of both.

**Current windows, as the code applies them**

- **Snooze:** no lookback window. A snooze filter applies until its `expiration` timestamp, and expired filters are ignored (`signal/service.py:743`).
- **Per-filter dedup window:** `SignalFilter.window`, in **seconds**, counted back from now (`service.py:846`). The model's pydantic default is 600 (10 minutes), and the column default is 3600 (1 hour).
- **Default dedup window** (filters absent): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, **minutes**, default 45 (2700 seconds), converted with `* 60` (`config.py:95`, `service.py:805`).

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. Canary instances are no longer deduplicated, and canary instances are excluded as dedup matches in both the default and filter paths. The default window was still hard-coded to 1 hour.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The hard-coded 1-hour default window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes**. The default window is therefore 15 minutes shorter than before unless the environment sets it.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*. The commit says "simplify", but it changed behavior. In `filter_snooze`, an expired snooze filter used to `continue` to the next filter. It now `break`s out of the loop, so any later active snooze filter in the list is no longer checked. Merging the mode and action checks into one condition doesn't change the outcome.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*. This commit changed the unit of the per-filter window. The code used to call `timedelta(minutes=f.window)`. It now calls `_window_start(f.window)`, which treats the value as seconds, matching the model's comment and defaults. A filter with `window=600` used to look back 600 minutes (10 hours), and now looks back 600 seconds (10 minutes). Stored values were not migrated, so existing filters now look back 60 times less far than their saved numbers suggest. I didn't check whether the UI labels this field in seconds, and I didn't check production data.

Commits that touched nearby code but did not change the snooze or dedup decision: `5e136d7b`, `d2675cf4`, and `4474af25`. `4474af25` only added logging of `filter_action`.

I haven't changed any code.

----- next turn -----

The window bug is fixed. A deduplication filter's window now means minutes, as the UI says, so a filter set to 30 groups instances up to 30 minutes apart.

**Cause:** `917a0b7b` (2025-08-14, *refactor(signal): share the lookback window computation*). It changed the per-filter window from `timedelta(minutes=f.window)` to a seconds-based helper. A filter set to 30 in the UI now looks back 30 seconds, so two instances ten minutes apart never match.

**Fix** (`src/dispatch/signal/service.py`):
- `_window_start` now takes minutes, and both callers pass minutes. The default-window path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, so it still gives 45 minutes.
- The comment on the filter window now says minutes, as entered in the UI.
- Existing filters need no edits or migration. Stored values were never converted, so a stored `30` means 30 minutes again.
- `src/dispatch/signal/models.py`: the column comment said seconds and "1 hour". It now says minutes.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_deduplicate_window_is_minutes`, parametrized:
- An instance 10 minutes old with a window of 30 is deduplicated. This case fails on the old code.
- An instance 40 minutes old with a window of 30 is not deduplicated. This case passes on both versions and guards the upper bound.

I added `import pytest` at the top of the file for the parametrize decorator.

**Verification:** Full `python -m pytest` gives 8 failed, 367 passed, 4 skipped. The 8 failures are the same pre-existing ones as before (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`). The 367 passes include the two new cases.

**Left alone, for you to decide:**
- The column default (`window = 3600`) and the API default (`window: int = 600`) are unchanged. Read as minutes, they now mean 60 hours and 10 hours for filters created without a window. Before `917a0b7b`, the code also read them as minutes, so this isn't a regression. The comment's intent of "1 hour" would need a default of 60.
- `086dc910` changed the snooze loop from `continue` to `break` when it meets an expired snooze. That stops it from checking later active snooze filters, which can let an instance through that a later snooze should have caught. It's unrelated to windows, so I didn't change it.
- I haven't checked production data, so I can't confirm the two cases on that signal came from this bug alone.

Nothing is committed.

----- next turn -----

The cause is `086dc910` (2025-08-07, *refactor(signal): simplify snooze filter checks*). I changed its `break` back to `continue` in `filter_snooze`, and the test passes.

**Cause:** when `filter_snooze` met an expired snooze, it did `break`, so the loop stopped and never reached the valid snooze after it. In the Okta case, if the expired filter comes first, the valid one is never checked. That's why new instances for that user weren't snoozed. The earlier commit `086dc910` had changed `continue` to `break` while presenting the change as a simplification.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): an expired snooze now `continue`s to the next filter, so every active snooze is checked. Nothing else in the function changed.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_expired_before_valid`. It attaches an expired snooze first and a valid one second, both matching the same entity, and expects the instance to be snoozed. It passes with the fix. Without the fix it fails.

**Verification:** `python -m pytest` gives 8 failed, 368 passed, 4 skipped. The 8 failures are the same pre-existing ones as before. The 368 passes include the new test.

Nothing is committed. Notes:
- The snooze fix and the earlier window fix are both in `service.py`, so the commit should include both or be split with care.
- I haven't checked the Okta data in production, so I can't confirm that this filter order caused the issue there.

----- next turn -----

## Recap

**Weekly reminders (Monday bug).** Weekly close and stable reminders stopped after mid-August, while daily triage reminders kept arriving. `_is_reminder_day` in `src/dispatch/case/scheduled.py` compared `calendar.MONDAY` (0) with `date.isoweekday()` (1 for Monday), so the check was always false. Commit `c509d45e` introduced it. The scheduler restarted on image `main-81d8ae42` on 2025-08-13, and the first Monday with no reminders was 2025-08-18. The fix uses `weekday()`, and a parametrized test covers Monday, Tuesday, and Sunday.

**Evening TypeError.** The case close reminder subtracted `case.triage_at` from the current time. `triage_at` is only set by the triage transition flow, so cases that reached triage another way raised a TypeError. The job now falls back to `created_at`, and three tests cover missing `triage_at`, a recent case without it, and a set `triage_at`. I could not confirm which case is failing, because the logs have no case IDs. The likely path is the Slack reopen button, which bypasses the transition flow. That path is unchanged.

**Signal deduplication and snoozing.** Three commits from the batch broke signal handling, and I fixed each one with a regression test:
- `917a0b7b` treated per-filter deduplication windows as seconds instead of minutes. A window of 30 looked back 30 seconds, so instances ten minutes apart were not grouped. The window is back in minutes, and stored values need no edits.
- `086dc910` changed the snooze loop from `continue` to `break` on an expired snooze, so a valid snooze later in the list was never checked. It is back to `continue`.
- `a348bbd2` is the commit that changed canary deduplication. It stopped canary signals from being deduplicated and excluded them as matches. I didn't change this behavior, and I'm listing it as the CANARY commit because it's the one that changed it.

Full test run: 8 failed, 368 passed, 4 skipped. The 8 failures are pre-existing and unrelated to these changes. Nothing is committed.

**Open items for you:**
- The stored window defaults (`window = 3600` on the model, `window: int = 600` in the API schema) now read as 60 hours and 10 hours. Before `917a0b7b` they meant the same, so this is not a new regression, but the comment said "1 hour." I did not change them.
- The `reopen_button_click` path in Slack still sets the case status directly and bypasses the transition flow.

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