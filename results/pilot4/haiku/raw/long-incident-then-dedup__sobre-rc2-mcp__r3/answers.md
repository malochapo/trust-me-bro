**Root cause:** the refactor in `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. The new helper compares ISO weekday to `calendar.MONDAY`:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Monday is 0 in `calendar`'s weekday numbering). I confirmed both values in the sandbox. The helper therefore returns False every day. The old code compared against `1`, which was correct. Because `case_close_reminder` and `case_stable_reminder` both call `_is_reminder_day()` and the `q >= 1` check still passes, the weekly close reminders never send. `case_triage_reminder` has no weekday gate, so the daily triage reminders keep arriving.

**Evidence from the logs:**
- Monday 2025-08-11 (old code still in memory): 5 "Case close reminder sent" lines.
- Monday 2025-08-18 (new code): zero close reminders. The same run sends "Case triage reminder sent" and "Incident close reminder sent", which fits the symptoms you described.

**Which deploy shipped it:** the code went live with the scheduler and web restart at **2025-08-13 16:40:11 UTC** (09:40 PT, Wed). The scheduler logs show `Starting scheduler...` on pod `scheduler-mhtsgqwwx-q5q2n`, and the web pod `web-5dkmr9s9s-xxktx` starts at the same time. The previous process (`scheduler-xdp7k6gs2q-w6cj7`, started 07-30) was still running the old code on Monday 08-11 and on the 08-12 18:00 UTC run. The first commit containing the bug is `c509d45e`, merged 2025-08-12 14:05 PT, which is before that restart.

Caveats:
- The repo has no release tag after 2024, and the logs don't record an image tag or release name. Production deploys run from a published GitHub release through `publish-image.yml`, so I can't name the exact release from here. The restart time above is the evidence I have.
- Separately, the logs show `TypeError: ... 'NoneType'` from `case_stable_reminder` and `case_close_reminder` through 08-13. That looks like the `stable_at`/`triage_at` None crash that `32fa810f` (08-11) was meant to fix. Either the 08-13 build predates that fix or the fix is incomplete. I haven't checked which, and it's worth confirming before the fix ships.

**Suggested fix (not applied):** compare against Python weekday numbering, e.g. `date.today().weekday() == calendar.MONDAY`, or go back to `isoweekday() == 1`. Either way, add a test that pins Monday with `freezegun` or a fixed date. Nothing in the repo has been changed.

----- next turn -----

The reminder bug is fixed and there is a regression test for it. The eight other failures in the full suite also happen on the untouched code.

**The fix** (`src/dispatch/case/scheduled.py:33`): the helper now uses `date.today().weekday() == calendar.MONDAY`. Both sides use `calendar`'s numbering, where Monday is 0. The previous `isoweekday()` returns Monday as 1, so the comparison never matched.

**The regression tests** (`tests/case/test_case_scheduled.py`, new file):
- `test_is_reminder_day` checks all seven weekdays. Only Monday returns True. This is the test that would have failed on the original bug.
- `test_case_close_reminder_sent_on_monday` and `test_case_stable_reminder_sent_on_monday` check that a long-running triage or stable case gets a reminder on a Monday.
- `test_case_close_reminder_not_sent_on_tuesday` checks that the same case gets no reminder on a non-Monday.

The tests pin the date with a `FixedDate` stand-in for `date` and call the task bodies directly through `scheduler.registered_tasks`. The reminder sender is mocked, so these tests don't touch the database.

**Verification:**
- With the original `isoweekday()` line restored, 3 of the new tests fail. With the fix, all 10 pass.
- Full suite with `python -m pytest tests`: 369 passed, 4 skipped, 8 failed. All 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those same 8 on the original code, and they fail there too. They're unrelated to this change, and I haven't investigated them.

Nothing is committed. The working tree has the modified `scheduled.py` and the new test file. Once the fix ships, the 2025-08-18 Monday run is the one that would have shown the problem.

----- next turn -----

The close reminder no longer crashes on cases without `triage_at`, and those cases now count from when they were created. I've added tests for both cases. I haven't confirmed this against production data, though.

**What causes the TypeError:** `case_close_reminder` subtracts `case.triage_at` from the current time. For some triage cases that field is NULL, and the subtraction raises `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try/except` catches it, so the other cases still run, but the NULL-timestamp case never gets its reminder.

The likely source is the migration `391f7c3e6992` (2022-08-01), which added `triage_at` as a nullable column with no backfill. Any case already in triage on that date kept NULL and stays in triage, so it hits the error every evening. The logs don't include case IDs, so I can't prove this from them. To confirm, run this against the production database:

```sql
SELECT count(*) FROM "case" WHERE status = 'triage' AND triage_at IS NULL;
```

A count above zero that matches the number of TypeErrors per run would confirm it.

**The fix** (`src/dispatch/case/scheduled.py:47-50`):

```python
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

**Tests** (`tests/case/test_case_scheduled.py`): two new cases.
- A triage case with NULL `triage_at` created 30 days ago gets a reminder on Monday.
- The same kind of case created 2 days ago gets none.

I checked that the first test fails when the fallback is removed. The full suite gives 371 passed, 4 skipped, and the same 8 unrelated failures as before.

Two things I didn't change:
- `case_stable_reminder` still skips cases with no `stable_at`. You asked for the fallback only on the close reminder, so I left it alone. Say if you want the same fallback there.
- The Slack `reopen_button_click` handler sets `status = triage` without running the triage transition flow, so it can still leave `triage_at` unset for new cases. I didn't touch it, but it's the place to fix if the NULLs keep appearing after this change.

Nothing is committed.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed how signal instances are snoozed or deduplicated. I read each commit's diff and the current code in `src/dispatch/signal/service.py`. I changed nothing.

**Commits**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - Canary instances skip deduplication entirely: `filter_dedup` returns early when `signal_instance.canary` is set.
   - Canary instances are also excluded from the candidate matches in both dedup queries (`~SignalInstance.canary`).
   - No window change.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - The window for signals with no dedup filter was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), default **45 minutes**.
   - So the default went from 60 to 45 minutes. The code applies it as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - This is labeled a refactor but changes behavior in `filter_snooze`:
     - An expired snooze filter now `break`s the loop instead of `continue`ing. Any later snooze filters on the signal are no longer checked.
     - The warnings for a filter with no mode or no action are gone. Those filters are now skipped silently.
   - The snooze expiration is an absolute timestamp, not a window.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Adds `_window_start(seconds)`. Per-filter dedup windows are now read as **seconds**: `_window_start(f.window)`. Before this commit the code multiplied them as **minutes** (`timedelta(minutes=f.window)`).
   - The model comment already says seconds (`models.py:206`, default `60 * 60` = 1 hour). The schema default in `SignalFilterBase` is `window: int | None = 600`, which is 10 minutes.
   - This commit changes the effective window for any existing filter whose stored value was set under the minutes reading, by a factor of 60. I did not check whether any migration converts stored values.

**Current values and units**

| Setting | Value | Unit |
|---|---|---|
| Snooze | absolute `expiration` datetime; no window | — |
| Default dedup (no filter) | 45 (env `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) | minutes |
| Per-filter dedup `window` | stored value; model default 3600, schema default 600 | seconds |

**Other commits:** the `-S` search also matched `5e136d7b`, `dee1699d`, `90f73fe2`, `01c28ff0`, `4474af25`, `d2675cf4`, and `5e136d7b`. I did not open their diffs, so I can't say they leave these paths unchanged. I also did not check `ENV`-level or database overrides of the window values.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). It started reading the stored `window` as seconds, but the UI and the stored filters use minutes. A 30 therefore became a 30-second window, so instances 10 minutes apart never grouped. The earlier commit `086dc910` doesn't affect the window.

**Fix** (`src/dispatch/signal/service.py:845-846`): the window is converted from minutes to seconds before use.

```python
# SignalFilter.window is entered in minutes (see the signal filter form)
window = _window_start(f.window * 60)
```

The UI's "Window (minutes)" field offers 5, 10, 15, 20, and 30. Existing filters keep their stored numbers and now mean what the UI shows, so none need editing.

**Regression test** (`tests/signal/test_signal_service.py`, `test_filter_dedup_window_is_minutes`): an earlier instance is 10 minutes old, and a later instance for the same entity is checked against a deduplication filter.
- Window 30 must deduplicate. This case failed on the code before the fix (`filter_action` was `None`), which confirmed the bug.
- Window 5 must not deduplicate. This pins the other side of the unit.

`python -m pytest tests/signal` against the local PostgreSQL gives 34 passed, 1 skipped.

**Two related edits:**
- `src/dispatch/signal/models.py`: the column comment now says minutes, and the column default changed from `60 * 60` to `60`. Under the minutes reading, the old default would have been 60 hours, not the 1 hour the comment describes. This only affects new rows that don't set a window, and no migration is needed.
- The file changed on disk after I last read it. I checked the current diff, and it matches my edit, so I left it as is.

**Not changed:** the API schema default `SignalFilterBase.window = 600` (`models.py`, around line 282) is still 600, which now means 10 hours for any request that omits `window`. I don't know the intended value, so I left it. Tell me which value you want and I'll set it.

I didn't run the full suite. The earlier uncommitted changes to `scheduled.py` and its test file are still in the tree, and nothing is committed.

----- next turn -----

The cause is commit `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks"). In `filter_snooze` it changed the handling of an expired snooze filter from `continue` to `break`. So when a signal has an expired snooze filter before an active one, the loop stops at the expired filter and never checks the active one. For the "Okta: Impossible travel" case, the expired filter comes first, so new instances for that user are not snoozed.

**Fix** (`src/dispatch/signal/service.py`, `filter_snooze`): the expired branch goes back to `continue`.

```python
if f.expiration.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
    continue
```

**Regression test** (`tests/signal/test_signal_service.py`, `test_filter_actions_snooze_after_expired_filter`): a signal has an expired snooze filter followed by an active one for the same entity. The instance must be snoozed. The test failed before the fix and passes after it.

`python -m pytest tests/signal` against the local PostgreSQL gives 35 passed, 1 skipped.

`086dc910` also removed the warnings for snooze filters with no mode or no action, so those filters are now skipped silently. I left that as it was, since it doesn't cause this bug. Say if you want the warnings back.

Nothing is committed. The earlier uncommitted changes to `scheduled.py`, the signal models and service, and the test files are still in the working tree.

----- next turn -----

**Weekly reminders (Monday case close and stable reminders)**

Monday reminders stopped after commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"). That commit changed `_is_reminder_day()` in `src/dispatch/case/scheduled.py` to compare `date.today().isoweekday()` with `calendar.MONDAY`. `calendar.MONDAY` is 0, and `isoweekday()` returns 1 for Monday, so the check never matched. I changed it to `date.today().weekday() == calendar.MONDAY`. Regression tests are in `tests/case/test_case_scheduled.py`, covering each weekday, the close and stable reminders, and the new fallback. I checked that the weekday tests fail with the bug reintroduced.

The deploy that shipped it is not confirmed. The repo tags stop in 2024, and the logs carry no image tag. The scheduler restarted at 2025-08-13 16:40 UTC, which is the likely deploy, but that is not proven.

**Evening TypeError**

The close reminder subtracted `case.triage_at` from the current time. Some cases in triage have `triage_at` NULL, so each evening's run raised a `TypeError` for those cases. The likely source is migration `391f7c3e6992` (2022-08-01), which added `triage_at` with no backfill. The fix uses `triage_at or created_at`. This is not yet confirmed in production. The check is `SELECT count(*) FROM "case" WHERE status = 'triage' AND triage_at IS NULL;`. Also, `reopen_button_click` in the Slack plugin sets `status = triage` without running the flow that sets `triage_at`, so new NULLs can still appear.

**Signal deduplication and snoozing**

- Windows: commit `917a0b7b` (2025-08-14) read the stored filter `window` as seconds. The UI labels it "Window (minutes)", so a 30-minute window became 30 seconds. The fix converts minutes to seconds (`f.window * 60`) in `src/dispatch/signal/service.py`. The column default changed from 60 × 60 to 60, and its comment now says minutes. The regression test is `test_filter_dedup_window_is_minutes`. The signal suite passes: 34 passed at that point, 1 skipped.
- Snoozing: commit `086dc910` (2025-08-07) changed `continue` to `break` on an expired snooze filter, so a later active filter on the same signal was never checked. The fix restores `continue`. The regression test is `test_filter_actions_snooze_after_expired_filter`. The signal suite passes: 35 passed, 1 skipped.
- Canary signals: `a348bbd2` (2025-05-29) made canary signals skip deduplication, which is intended. It is not a bug.

Still open: the 8 test failures in the full suite predate today's work (`tests/ai/test_ai_service.py` ×6, `tests/database/test_service.py`, `tests/entity/test_entity_service.py`). The `SignalFilterBase` schema default `window = 600` is now 10 hours, and I left it unchanged. Nothing is committed.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: unknown (not recorded in repo or logs; scheduler restart 2025-08-13 16:40 UTC is the likely deploy)
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```