The weekly reminders stopped because of a comparison bug in `_is_reminder_day()`. It shipped in production on 2025-08-13 as image `main-81d8ae42`. I haven't changed any code.

**Root cause**

`src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so this is always `False`. Both `case_close_reminder` and `case_stable_reminder` gate their sends on `q >= 1 and _is_reminder_day()`, so the weekly close and stable reminders never fire. `case_triage_reminder` doesn't call this check, which is why the daily triage reminders still arrive.

**Commit that introduced it**

`c509d45e` — "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()` in both places. The refactor is what changed the behavior: the old literal `1` was correct.

**Deploy that shipped it**

- `c509d45e` is on `main`, and the first image containing it is `registry.example.com/dispatch:main-81d8ae42`. The earlier image `main-b05613b5` does not contain it.
- Both the web and scheduler containers started on that image on 2025-08-13 at about 16:40 UTC (kubelet lines in `api.log` and `scheduler.log`). That is the only redeploy in the logs between 07-30 and 08-20.
- The logs confirm the timing. Monday 2025-08-11, still on the old image, sent 5 close/stable reminders. Monday 2025-08-18, on the new image, sent 0, while 1 triage reminder still went out.

`81d8ae42` was the head of `main` at deploy time, so that deploy also carried `32fa810f` and `7c446bd6`. Only `c509d45e` changed this logic.

**Secondary issue (not the cause)**

The daily `case_close_reminder` logs a `TypeError: datetime - NoneType` for cases whose `triage_at` is `None` (`scheduled.py:47`). This happens every day through 2025-08-20. The per-case `try/except` contains it, so other cases are unaffected, but those cases are skipped. It's worth a separate fix.

**Proposed fix (not applied)**

Make the check match `isoweekday()`, e.g. `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based, like `calendar.MONDAY`), or compare against `calendar.MONDAY + 1`. A regression test that pins a Monday date would catch this next time.

----- next turn -----

The weekly reminder bug is fixed and covered by a regression test. The full suite has 8 failures, and they also fail on the untouched code, so they are not from this change.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. The old `isoweekday()` is 1-based, so the check never matched.

**The regression test** (new file `tests/case/test_case_scheduled.py`): it patches `date` in the scheduled module and checks Monday 2025-08-18 plus the following six days. Only Monday should return true.
- With the fix, all 7 cases pass.
- With the old expression restored, the Monday case fails, so the test catches this bug.

**Full suite** (`python -m pytest`): 366 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those same 8 with the fix stashed and they still fail, so they predate this change. I didn't investigate them further.

**Not done**: I didn't add a test that drives `case_close_reminder` or `case_stable_reminder` end to end on a Monday. The scheduler decorators make that harder to set up, and the helper test covers the broken line. I also didn't commit anything.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and the nightly TypeError is gone. The new tests pass, and I confirmed the fixed test fails on the old line.

**What causes it:** `case_close_reminder` subtracts `case.triage_at`, which is null for some triage cases. `triage_at` is only set by `case_triage_status_flow`, which the transition dispatcher calls for new→triage and closed→triage. The catch-all `(_, triage)` branch (`src/dispatch/case/flows.py:766`) only logs a warning and never sets it. So a case that moves into triage from escalated or stable keeps a null `triage_at`. The logs don't contain that warning, so I can't tie the specific logged cases to this path. It's the only path I found that produces a triage case without the timestamp.

**The fix** (`src/dispatch/case/scheduled.py:47-49`): `started_at = case.triage_at or case.created_at`, then the existing weekly check runs on `started_at`. `created_at` is stored as a naive timestamp, the same type the triage reminder already subtracts from.

**Tests** (`tests/case/test_case_scheduled.py`): four cases call the real job body through the scheduler registry, with the Monday check and the messaging call patched.
- No `triage_at`, created 8 days ago: sent.
- No `triage_at`, created 2 days ago: not sent.
- `triage_at` 8 days ago, created 30 days ago: sent, so `triage_at` still wins when present.
- `triage_at` 2 days ago, created 30 days ago: not sent.

**Full suite:** 370 passed, 4 skipped, and the same 8 failures as before (AI service, one database test, one entity test), which also fail on the untouched code.

**Not changed:**
- The stable reminder still skips cases without `stable_at` (from the earlier fix). You asked about the close job only.
- The root cause in the dispatcher is still there. Setting `triage_at` in the `(_, triage)` branch would stop new cases from getting null timestamps. I'd suggest doing that as a separate change.

Nothing is committed.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed the snooze or dedup decision or its windows. I made no code changes.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals." Canary signal instances are now skipped by dedup, both the default path and the filter path. Canaries are still checked for snooze.
2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable." The default window (no dedup filters on the signal) was a hardcoded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95-97`, default **45 minutes**.
3. **`086dc910`** (2025-08-07), "simplify snooze filter checks." The expired-snooze branch in `filter_snooze` changed from `continue` to `break`. Before, an expired snooze filter was skipped and later snooze filters still ran. Now the first expired snooze filter ends the snooze check, so a later active snooze filter on the same signal is not applied. The commit also dropped the missing-mode and missing-action warnings, which doesn't change the outcome.
4. **`917a0b7b`** (2025-08-14), "share the lookback window computation." Despite the "refactor" title, this changed a unit. The filter-dedup window used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats the value as **seconds**. That matches the model comment in `src/dispatch/signal/models.py:206-208`. A stored window now looks back 60 times less far than the same number did before. I did not check how the UI or API sets this value, so I can't say whether existing filters are affected.

**Current values as the code applies them**

- **Snooze:** no lookback window. A snooze filter applies while `expiration` is in the future (`filter_snooze`, `src/dispatch/signal/service.py:743-781`). The `window` field is not used for snooze. Filters with no expiration are skipped with a warning.
- **Default dedup (signal has no dedup filters):** 45 minutes, computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. It matches only against instances that have a case.
- **Dedup filter:** the window is `SignalFilter.window` in **seconds**. The model default is 3600 (1 hour). The API schema default is 600 (10 minutes). Matching uses the earliest instance in the window.

**Indirect change, not a decision change**

- **`d2675cf4`** (2025-07-03), "mask sensitive raw fields before processing." It redacts `raw` before entity extraction (`src/dispatch/signal/flows.py:58`). Dedup matches on entities, so it can change which instances match, but it does not change the snooze or dedup logic or its windows.

**Other commits**

`4474af25` only adds logging of the filter outcome.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the filter window from minutes to seconds. The UI labels the field "Window (minutes)" with options 5 to 30, and the code treated the stored 30 as 30 seconds. Your two instances ten minutes apart fell outside that window, so both opened cases. The field's minutes meaning dates to 2023 (`0b6e867b`).

**Fix** (`src/dispatch/signal/service.py`)
- `_window_start` takes minutes again. The filter path passes `f.window` directly, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`.
- The comment in `src/dispatch/signal/models.py` now says minutes.
- No data change is needed. Existing filters store minutes, so their values work as the UI shows them.

**Regression test** (`tests/signal/test_signal_service.py`)
- `test_deduplicate_filter_window_is_in_minutes` is parametrized. An earlier instance is created ten minutes before the new one. A window of 30 must deduplicate, and a window of 5 must not.
- I also added the `import pytest` the test needs.
- With the seconds helper restored temporarily, the window-30 case fails. With the fix, both cases pass.

**Results**
- `python -m pytest`: 372 passed, 4 skipped, 8 failed. The 8 failures are the same ones from before (AI service, one database test, one entity test) and also fail without my changes. The 2 new tests account for the increase from 370 to 372.
- Nothing is committed.

**Left unchanged, for you to decide**
- The API defaults are `SignalFilterBase.window = 600` (`models.py:282`) and the column default `60 * 60` (`models.py:206-207`). Read as minutes, these are 10 hours and 60 hours. The 1-hour comment on the column no longer matches its value. Those defaults were already read as minutes before `917a0b7b`, so this change restores the old behavior. I didn't change them because changing them would alter what new filters created without a window do.

----- next turn -----

The cause is commit `086dc910` ("refactor(signal): simplify snooze filter checks", 2025-08-07). In `filter_snooze` (`src/dispatch/signal/service.py:762`) it changed the expired-snooze branch from `continue` to `break`. An expired snooze filter then ends the whole loop, so a valid snooze listed after it is never checked. That's why the "Okta: Impossible travel" instances for that user are no longer snoozed.

**Fix:** the expired branch is back to `continue`, so expired filters are skipped and the loop goes on to the next one.

**Regression test:** `test_snooze_checks_later_filters_after_expired_one` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter, then a valid one, both matching the same entity, and checks that a new instance for that entity is snoozed.
- With `break` restored, the test fails.
- With `continue`, it passes.

**Full suite** (`python -m pytest`): 373 passed, 4 skipped, 8 failed. The 8 failures are the same ones from before (AI service, one database test, one entity test) and also fail without my changes.

Nothing is committed. Your report also covers the two dedup-window commits from earlier, but the window fix and this one are separate changes, so I've kept them separate in the working tree.

----- next turn -----

## Recap of today's work

**Investigation 1: missing Monday reminders for long-running cases**
- Weekly Monday reminders for long-running triage and stable cases stopped after the 2025-08-13 deploy. The daily triage reminders kept arriving.
- The cause is a weekday comparison bug in `_is_reminder_day()`. The check compared `date.isoweekday()`, which is 1-based (Monday = 1), against `calendar.MONDAY`, which is 0-based (Monday = 0). The check was therefore never true.
- The bug came from commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) and shipped in image `main-81d8ae42`.
- Fix: `date.today().weekday() == calendar.MONDAY`. The regression test is in `tests/case/test_case_scheduled.py`. It fails on the old line and passes on the fix.
- First missed Monday: 2025-08-18. The previous Monday, 2025-08-11, ran on the earlier image.

**Investigation 2: close-reminder TypeError every evening**
- The `case_close_reminder` job subtracted `case.triage_at` from the current time. `triage_at` is null for some triage cases, which raised a TypeError each evening.
- The likely path is the catch-all `(_, triage)` transition in `src/dispatch/case/flows.py:766`, which never sets `triage_at`. I did not confirm this from production logs.
- Fix: count from `case.triage_at or case.created_at`, so those cases still get their weekly reminder. The tests are in `tests/case/test_case_scheduled.py`.

**Investigation 3: snooze and dedup regressions (from the signal reports)**
- Deduplication windows: commit `917a0b7b` ("share the lookback window computation", 2025-08-14) changed the filter window from minutes to seconds. The UI labels the field "Window (minutes)", so a window of 30 was read as 30 seconds. Fixed in `src/dispatch/signal/service.py` (`_window_start` takes minutes again), with a regression test in `tests/signal/test_signal_service.py`. No stored data needed changing.
- Snoozing: commit `086dc910` ("simplify snooze filter checks", 2025-08-07) changed `continue` to `break` on expired snooze filters. An expired filter ended the loop, so a valid snooze later in the list was never applied. Fixed back to `continue`, with a regression test.
- Canary signals: commit `a348bbd2` ("don't dedup on canary signals", 2025-05-29) changed how canaries are deduplicated. Canaries are now skipped by both deduplication paths.

**Test status:** `python -m pytest` gives 373 passed, 4 skipped, 8 failed. The 8 failures are in the AI service, one database test, and one entity test. They also fail without these changes and are not related to this work.

**Not committed.** The changes are in the working tree (`scheduled.py`, `signal/service.py`, `signal/models.py`, and two test files). Two defaults still need a decision: the API default `window = 600` and the column default `60 * 60`, which now read as minutes.

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