**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday check into `_is_reminder_day()` and compares `isoweekday()` to `calendar.MONDAY`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # src/dispatch/case/scheduled.py
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (Python's `weekday()` convention). I checked both in the sandbox: `calendar.MONDAY = 0`, and `date(2025,8,18).isoweekday() = 1`. So the check is never true, on any day. The original code was `date.today().isoweekday() == 1`, which was correct.

The helper is used only by `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases), which is why only the Monday weekly reminders stopped. `case_triage_reminder` doesn't call it, so the daily triage reminders still go out.

**Deploy that shipped it:** the scheduler started on image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40Z (`scheduler.log` line 18851). `c509d45e` is an ancestor of `81d8ae42` (the `81d8ae42` commit is "fix(case): exclude resolved_by in update (#6183)"). The previous scheduler image was `main-b05613b5`, started 2025-07-30, and it doesn't contain the refactor.

**Log evidence:**
- Monday 2025-08-11 (old image): the scheduler sent several "Case close reminder sent" and stable-case reminders.
- Monday 2025-08-18 (new image): `case_stable_reminder` and `case_close_reminder` both ran with no reminder sends. The only Monday sends were incident and triage reminders.
- The first Monday after the deploy was 08-18, which is why the problem started "mid-August".

**Unrelated noise in the logs:** `case_close_reminder` and `case_stable_reminder` also log `unsupported operand type(s) ... NoneType` errors for cases with a null `triage_at` or `stable_at`. The per-case try/except catches them, so they don't stop the other cases. The stable one was fixed in `32fa810f` on 2025-08-11. The triage one is still present, but it does not explain the missing reminders.

**Suggested fix (not applied, per your request):** change `_is_reminder_day()` to compare against `1`, or use `date.today().weekday() == calendar.MONDAY`. Then add a unit test that pins a known Monday date so this can't silently regress.

----- next turn -----

The Monday reminder check is fixed, and there is a regression test that fails on the broken code and passes on the fix. The fix is uncommitted in the working tree.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now compares `date.today().weekday()` to `calendar.MONDAY`. Both use the 0-based convention, so Monday matches again. I kept the `calendar` constant rather than writing `== 1`.

**Regression test** (new file `tests/case/test_case_scheduled.py`, 9 tests):
- `test_is_reminder_day` checks Monday is true and Tuesday through Sunday are false, with `date` patched.
- `test_case_stable_reminder_sends_on_monday` runs the stable-case reminder task body on a Monday against a real case with `stable_at` 8 days ago, and asserts that a reminder is sent.
- `test_case_stable_reminder_skips_non_monday` checks that nothing is sent on a Tuesday.

The task body is looked up from `scheduler.registered_tasks`, because `scheduler.add` returns `None` and the module-level names are `None`. I reintroduced the broken `isoweekday() == calendar.MONDAY` temporarily: `test_is_reminder_day[Monday]` and `test_case_stable_reminder_sends_on_monday` failed, and then I restored the fix.

**Test results:**
- `python -m pytest tests/case/test_case_scheduled.py`: 9 passed.
- `tests/case`, `tests/case_type`, `tests/case_cost`: 52 passed.
- Full `python -m pytest`: 368 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (5), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). The same 8 fail on a clean HEAD, so they are unrelated to this change.

I did not commit anything. The regression test covers the stable-case reminder. The triage-case reminder (`case_close_reminder`) uses the same helper, so the helper test covers it too, but it has no end-to-end test of its own.

----- next turn -----

The evening `TypeError` comes from `case_close_reminder` subtracting `None` from `case.triage_at`. I've added the `created_at` fallback you asked for and a regression test. Nothing is committed.

**Cause:** `triage_at` is set in exactly one place, `case_triage_status_flow` in `src/dispatch/case/flows.py:594`. That flow runs only for `new→triage` and `closed→triage`. Two other paths put a case into `triage` without it:
- **Transition dispatcher catch-all:** the `(_, triage)` branch at `flows.py:766` only logs a warning. It covers `stable→triage` and `escalated→triage`, and a case can reach `stable` directly from `new` (`flows.py:853`).
- **Slack reopen button:** `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427` assigns `status = triage` directly.

A case in that state stays in `triage` with `triage_at = NULL`. The job's per-case `try/except` catches the error, so the other cases still get reminders, but that case gets nothing and the error is logged every evening. The scheduler log has this error every evening from 2025-07-28 on.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`):
```python
# triage_at is not set for every case that reaches triage, so fall back to created_at
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

**Tests** (`tests/case/test_case_scheduled.py`, two added):
- `test_case_close_reminder_sends_on_monday`: a triage case with `triage_at` 8 days ago gets a reminder on a Monday.
- `test_case_close_reminder_without_triage_at_counts_from_created_at`: `triage_at=None` and `created_at` 8 days ago gets a reminder. This one fails with the `TypeError` if the fallback is removed.
- `test_case_close_reminder_without_triage_at_skips_recent_case`: `triage_at=None` and `created_at` 2 days ago gets no reminder.

Results: the 12 scheduled-reminder tests pass. The `tests/case`, `tests/case_type` and `tests/case_cost` run gives 55 passed.

**Not changed:** the root cause itself. `case_triage_status_flow` is still skipped on `stable→triage`, `escalated→triage` and the reopen button, so `triage_at` stays empty for those cases. Setting it in those paths would be a separate change. The stable-case reminder has a similar gap: it skips cases with no `stable_at` instead of falling back. Say if you want either handled.

----- next turn -----

## Recap

**Weekday bug:** Since 2025-08-13, the Monday weekly reminders for long-running triage and stable cases have not been sent. Daily triage reminders were not affected. `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the check never passed. Commit `c509d45e` introduced it in a refactor that moved the check into a shared helper. It shipped in scheduler image `main-81d8ae42`, which started on 2025-08-13 at 16:40Z. The last Monday with reminders was 2025-08-11, and the first missed one was 2025-08-18. The fix changes the check to `date.today().weekday() == calendar.MONDAY`. It is uncommitted in the working tree, with a regression test in `tests/case/test_case_scheduled.py` that fails on the old code.

**Evening TypeError:** `case_close_reminder` runs `utcnow() - case.triage_at`, and `triage_at` is NULL for some triage cases. The per-case `try/except` catches the error, so other cases are unaffected, but the affected case gets no reminder and the error is logged every evening. `triage_at` is set only in `case_triage_status_flow`, which is skipped for `stable→triage`, `escalated→triage`, and the Slack reopen button. The fix counts from `created_at` when `triage_at` is missing. It is also uncommitted, with tests.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at