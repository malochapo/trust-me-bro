The cause is commit `c509d45e`, a refactor that replaced the Monday check with a constant from a different day-numbering convention. It shipped to production in the 2025-08-13 deploy of image `main-81d8ae42`. I did not change any code.

**Root cause**

`src/dispatch/case/scheduled.py:31-33` (added by `c509d45e`, "refactor(case): share the weekly reminder check", Aug 12):

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The old inline check was `date.today().isoweekday() == 1`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (Python's `weekday()` convention). I confirmed both values locally: `calendar.MONDAY == 0`, and `isoweekday()` for 2025-08-04 is 1. So `_is_reminder_day()` returns False every day, and the weekly reminders are never sent:

- `case_close_reminder` (triage cases, line 49) calls it, so long-running triage cases get no reminder.
- `case_stable_reminder` (stable cases, line 95) calls it, so stable cases get no reminder.
- `case_triage_reminder` (daily, lines 58-78) does not use the helper, so the daily triage reminders still go out. This matches what you're seeing.

**Deploy that shipped it**

- The `b05613b5` deploy (image `main-b05613b5`) ran from 2025-07-30 17:10Z.
- The next deploy, image `main-81d8ae42`, rolled the web and scheduler pods on **2025-08-13 16:40Z**.
- `c509d45e` is an ancestor of `81d8ae42` and falls in that window, so `81d8ae42` is the deploy that shipped it.

**Log evidence**

- "Case close reminder sent" appears on Mondays 07-28 (4), 08-04 (6), and 08-11 (5). The 08-11 sends happened before the Aug 12 commit and the Aug 13 deploy.
- Monday 08-18 has no close or stable reminder sends, the first Monday under the new code.

**Side note, not the cause:** `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` on line 43 every day from 07-28 onward, because `case.triage_at` can be None. The per-case `try/except` contains it, so it does not stop the other cases, but it's worth a separate fix. The stable reminder already guards this with `if case.stable_at`.

**Suggested fix (not applied):** compare against the matching convention, e.g. `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`. Add a test that pins a known Monday, since nothing caught this.

----- next turn -----

The weekly reminder check is fixed, and the regression test is in place. Nothing is committed.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both `weekday()` and `calendar.MONDAY` use Monday = 0, so the two sides finally agree. The change is one line, and both the close and stable reminders go through this helper.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it replaces `date` in the scheduled module with a fake whose `today()` returns a chosen day. It then checks `_is_reminder_day()` for Monday, each of Tuesday through Sunday, and a Monday on the 18th of August 2025.
- Against the old code, the Monday case fails (`_is_reminder_day()` returns False).
- With the fix, all 7 cases pass.

**Test results**
- `python -m pytest tests/case`: 22 passed, which includes the 7 new cases.
- `python -m ruff check` on both changed files: all checks passed. The standalone `ruff` binary isn't installed here, so I didn't run `ruff format --check`.

I didn't run the full test suite, only the case tests. The `triage_at is None` error in `case_close_reminder` that I mentioned earlier is still there. It's a separate bug, so I left it alone.

----- next turn -----

The close reminder no longer crashes on cases without `triage_at`. Those cases are now counted from `created_at`, and a regression test covers it. Nothing is committed.

**What causes the TypeError:** `case_close_reminder` subtracts `case.triage_at` from the current time, and `triage_at` is NULL on some cases in triage. It is set only by `case_triage_status_flow`, and that flow doesn't run for every path into triage:
- Transitions escalated→closed, escalated→stable, and stable→closed skip it, so a case that was never triaged has no `triage_at`.
- The fallback `(_, triage)` branch in the status dispatcher logs a warning and doesn't set it.
- The Slack reopen button (`interactive.py:1427`) sets `status = triage` directly without any flow.

The scheduler logs don't name the cases, so I can't say which of these produced the current rows. Setting `triage_at` on every path into triage is a separate fix, and I haven't made it.

**The fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the count now starts from `case.triage_at or case.created_at`.

**The test** (`tests/case/test_case_scheduled.py`): it creates one triage case created 8 days ago and one created 2 days ago, both with no `triage_at`. It runs the task on a fake Monday and checks that only the 8-day-old case gets a reminder. It looks the task up in the scheduler registry because `scheduler.add` doesn't return the function. Reverting only the fallback makes it fail with the same TypeError.

**Results:** `python -m pytest tests/case` passes (23 tests), and `ruff check` passes on both files.

**Left unchanged:** `case_stable_reminder` still skips stable cases with no `stable_at`, so those cases still get no weekly reminder. You asked only about the close reminder, so I didn't change it.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or deduplication logic in `src/dispatch/signal/service.py`. Two of the window changes are unit-sensitive, and one of them looks like a regression.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29, "fix(signal): don't dedup on canary signals", #6026)
   - Canary instances skip deduplication entirely. They are also excluded as dedup candidates, both in the default check and in per-filter checks.
   - Window: none added. The default lookback was still hard-coded to 1 hour.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable")
   - The default lookback for signals with no dedup filter now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`).
   - Default is **45 minutes**, converted to seconds in code (`* 60`). It was previously a hard-coded 1 hour.
   - The `filter_signal` docstring still says "1-hour window", which is now stale.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks")
   - `filter_snooze` used to `continue` past an expired snooze filter. It now `break`s, so any later active snooze filter in the list is never checked.
   - Logging for filters with no mode or no action was removed. Those filters are now skipped silently.
   - Window: none. Snooze is governed by `expiration` (a timestamp), not a duration.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation")
   - Titled a refactor, but it changed units. The per-filter dedup window was previously `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats the value as **seconds**.
   - The model column `SignalFilter.window` defaults to **3600** seconds (`src/dispatch/signal/models.py:206`). The schema default is **600** (`models.py:282`).

**Windows as the code applies them today**

| Path | Window | Unit | Source |
|---|---|---|---|
| Default dedup (no filters on signal) | 45 | minutes (`* 60` to seconds) | `config.py:95` |
| Per-filter dedup | `SignalFilter.window`, default 3600 in model, 600 in schema | seconds | `service.py` `filter_dedup` |
| Snooze | none; uses `expiration` timestamp | — | `filter_snooze` |

**Likely regression: per-filter dedup units**

The UI still labels this field "Window (minutes)" and offers 5, 10, 15, 20, 30 (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:57`, `:196`). Since `917a0b7b`, the backend reads those values as seconds. A filter set to 10 minutes now looks back 10 seconds, and a filter that used to look back 10 hours (600 minutes) now looks back 10 minutes. I haven't checked the existing tests or any stored rows, so I can't say which filters are affected in production.

I haven't changed any code. I read the commit diffs with `git show` and did not run the test suite. I didn't inspect the other signal-directory commits since 2025-05-22 (`4474af25`, `d2675cf4`, `5e136d7b`), since their messages don't mention snooze or dedup.

----- next turn -----

The cause was `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the per-filter window from minutes to seconds. A window of 30 now looks back 30 seconds, so the instance ten minutes earlier falls outside it and the second instance opens its own case. I've restored minutes, so existing filters behave as they did before that commit, without being edited.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The per-filter path passes `f.window` directly, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default is now `60` minutes, which is still one hour, and the comment now says minutes. The old `3600` default was a seconds value, and it is now 60 hours under the minutes meaning. The column default is applied in Python, so no migration is needed.
- `tests/signal/test_signal_service.py`: added `test_filter_window_is_in_minutes`. It creates an instance ten minutes old, applies a dedup filter with window 30, and checks that a second instance joins the same case.

**Verification**
- The new test passes with the fix. With the seconds behaviour restored, it fails.
- `python -m pytest tests/signal tests/case -q`: 56 passed, 1 skipped.
- `ruff check` passes on the signal source and tests. `ruff format --check` flags `models.py` at line 416 (blank line before the forward references). That is outside my edit and was already there. The other two files it flagged, `test_signal_flow.py` and `test_signal_stats_service.py`, I didn't touch.

**Left alone**
- `SignalFilterBase.window` in `models.py` still defaults to `600`. That now means 600 minutes (10 hours). The UI always sends a window, so this only matters for API callers that omit it. Tell me if you want it changed.
- The `filter_signal` docstring still says "1-hour window" for the default, but the default is 45 minutes. That was already stale before this change.
- Nothing is committed.

----- next turn -----

The cause is `086dc910` ("simplify snooze filter checks", 2025-08-07). It changed the expired-filter branch in `filter_snooze` from `continue` to `break`. Any expired snooze filter that comes before a valid one ends the loop, so the valid filter is never checked and the new instance isn't snoozed.

**Fix** (`src/dispatch/signal/service.py`): the expired branch uses `continue` again, so the loop moves on to the next filter.

**Regression test** (`tests/signal/test_signal_service.py`, `test_filter_actions_snooze_after_expired_filter`): the signal has an expired snooze filter first and a valid one (30 days out) second, both matching the same entity. The instance must be snoozed.
- With the fix, the test passes.
- With `break` restored, it fails.

**Verification:** `python -m pytest tests/signal tests/case -q` gives 57 passed, 1 skipped. `ruff check` passes on the touched directories.

**Still uncommitted:** the working tree has this change plus the earlier ones (the case reminder fix, the dedup window fix). Nothing is committed.

----- next turn -----

## Recap

**Weekly reminders (investigation 1 and fix).** Assignees stopped getting the Monday close and stable reminders after the deploy on 2025-08-13. The cause was `_is_reminder_day` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so the check never matched. Commit `c509d45e` (2025-08-12, "share the weekly reminder check") introduced it, and it shipped in `main-81d8ae42`. The fix uses `weekday()`. A regression test in `tests/case/test_case_scheduled.py` fails on the old code and passes on the new.

**Evening TypeError (investigation 3).** The close reminder subtracted `case.triage_at` from the current time, and `triage_at` is NULL on some triaging cases. The job now counts from `triage_at or created_at`, and a test covers a case with no `triage_at`. I didn't confirm which production path leaves `triage_at` empty. The likely candidates are the transitions that skip `case_triage_status_flow` and the Slack reopen button, which sets the status directly. Stable reminders still skip cases with no `stable_at`, and I left that as it was.

**Deduplication windows (investigation 2).** Commit `917a0b7b` (2025-08-14) changed per-filter dedup windows from minutes to seconds. A window of 30 looked back 30 seconds, so instances ten minutes apart opened separate cases. The fix restores minutes and changes the `SignalFilter.window` column default to 60 (one hour). The regression test `test_filter_window_is_in_minutes` fails on the seconds behaviour and passes now.

**Snoozing (investigation 2, second report).** Commit `086dc910` (2025-08-07) changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. An expired filter earlier in the list stopped the loop, so a valid snooze filter after it was never checked. The fix restores `continue`, and `test_filter_actions_snooze_after_expired_filter` covers it.

**Canary signals.** Commit `a348bbd2` (2025-05-29, #6026) made canary signals skip deduplication and excluded them from dedup candidates. That behaviour is still in place, and I didn't change it.

**Default grouping window.** Signals with no filter group over 45 minutes. Commit `7a9fe810` made that value configurable, and before it the value was a hard-coded 1 hour.

Status: all of the above is in the working tree and uncommitted. `python -m pytest tests/signal tests/case` gives 57 passed, 1 skipped.

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