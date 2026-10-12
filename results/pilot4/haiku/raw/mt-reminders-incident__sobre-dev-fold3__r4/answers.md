The root cause is a bad weekday constant in the refactor commit `c509d45e`. It shipped to production in the 2025-08-13 16:40 UTC rollout of `main-81d8ae42`. I haven't changed any code.

**Root cause**

`c509d45e` ("refactor(case): share the weekly reminder check", Aug 12) moved the Monday check into a helper in `src/dispatch/case/scheduled.py:33`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` is 1-based (Monday = 1), but `calendar.MONDAY` is 0 (verified: `calendar.MONDAY = 0`, Monday 2025-08-18 has `isoweekday() = 1`). The comparison is therefore always false, so `case_close_reminder` and `case_stable_reminder` never send. The original code compared against the literal `1` (`date.today().isoweekday() == 1`), which was correct. The incident weekly check at `src/dispatch/incident/scheduled.py:229` still uses `== 1`, which is why incident reminders are unaffected.

The daily `case_triage_reminder` doesn't use this check at all, which is why those reminders still arrive.

**Evidence from the logs**

- Monday 2025-08-11 still sent close reminders (5 "Case close reminder sent" lines). That run was on the old image, `main-b05613b5`.
- Monday 2025-08-18 sent zero case close reminders. It was the first Monday on the new code. The only reminder sends that day were incident ones.
- The scheduler pod `scheduler-mhtsgqwwx-q5q2n` started with `main-81d8ae42` at `2025-08-13T16:40:06Z` (`scheduler.log:18851`). The web pod was rolled out to the same image at `16:40:07Z` (`api.log:13201`).
- `81d8ae42` is the head of the range that includes `c509d45e`, so the deploy that shipped the bug is the rollout of `main-81d8ae42` on 2025-08-13.

**Things that are not the cause**

- The per-case `datetime - None` tracebacks are a separate, already-fixed issue. `case.stable_at` was guarded by `32fa810f` (Aug 11), and `case_close_reminder` logs one caught `triage_at=None` error per day from July 28. These are caught per case, so they don't stop the other cases from being processed. They are worth a follow-up, but they are not why the Monday sends stopped.
- The logs stop at 2025-08-20, so I can't see later Mondays.

**Fix I'd propose (not applied)**

Change line 33 to `return date.today().isoweekday() == 1`, or to `date.today().weekday() == calendar.MONDAY` (0-based, which matches `calendar.MONDAY`). Add a test for the Monday check, since nothing caught this. Once that's deployed, the missed Monday reminders for 08-18 and later will not be re-sent automatically.

Do you want me to make that change and add the test?

----- next turn -----

I fixed the weekday check and added a regression test. The test fails on the old code and passes on the new code. All 22 tests in `tests/case` pass, run with `python -m pytest`.

**The fix** is in `src/dispatch/case/scheduled.py:33`. The helper now compares `date.today().weekday()` (0-based, Monday = 0) with `calendar.MONDAY` (also 0). Before, it compared `isoweekday()` (1-based) with `calendar.MONDAY`, so it was never true.

**The regression test** is in `tests/case/test_case_scheduled.py`. It patches `date.today()` and checks `_is_reminder_day()` for each day of the week from 2025-08-18 (Monday) to 2025-08-24 (Sunday). Against the unfixed code, the Monday case fails with `assert False is True`.

I didn't commit the change. Working tree: `M src/dispatch/case/scheduled.py` and `?? tests/case/test_case_scheduled.py`.

The reminders that were missed on 2025-08-18 and later Mondays won't be resent automatically. If you want them sent, that needs a separate decision.

----- next turn -----

The close-reminder TypeError is fixed, and the job now counts from `created_at` when `triage_at` is missing. All 23 tests in `tests/case` pass.

**What causes the TypeError**

`case_close_reminder` subtracts `case.triage_at` from `utcnow()`, and that field is `None` for some triage cases. The logs have 24 of these, one per evening, all the same `datetime - NoneType` error. Each one is caught per case, so the rest of the cases still get processed.

Triage cases normally get `triage_at` from `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). The reopen button doesn't go through that flow: `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427` sets `case.status = CaseStatus.triage` directly. A case that was closed without ever being triaged, then reopened, ends up in triage with `triage_at = None`. This is the most likely source, but I can't confirm it from the logs because they don't include case IDs.

**The fix** (`src/dispatch/case/scheduled.py`)

```python
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

**The test** (`tests/case/test_case_scheduled.py`)

`test_case_close_reminder_without_triage_at_counts_from_created_at` creates two triage cases with `triage_at=None`: one created 8 days ago (should be reminded) and one created 1 day ago (should not). It calls the real job body and mocks only the sender. With the fix reverted, the test fails; with the fix, it passes.

Two things came up while writing the test:
- `CaseFactory` ignores a `status` kwarg, because `tests/factories.py:794` defines `status = "New"` in `Params`. The test sets the status after construction. I didn't change the factory, since other tests may depend on it.
- `scheduler.add` returns `None`, so the test looks the job up in `scheduler.registered_tasks` and unwraps it.

**Not changed**

- The reopen bypass at `interactive.py:1427` is still there. Routing it through the transition flow would stop new cases from getting `triage_at = None`, but that's a separate change, so I left it alone.
- The stable reminder still skips cases without `stable_at` entirely, rather than falling back to a date. You only asked about the close reminder, so I didn't change it.

Nothing is committed.

----- next turn -----

**Recap**

- **Weekly reminders stopped after Monday 2025-08-11.** Monday 2025-08-18 was the first Monday with no case close or stable reminders sent. Daily triage reminders kept working.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Aug 12) moved the Monday check into `_is_reminder_day()`. It compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check was never true. The previous code compared with `1` and was correct.
- **Deploy:** the scheduler and web pods rolled out to `main-81d8ae42` on 2025-08-13 at 16:40 UTC. That head commit includes `c509d45e`.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `tests/case/test_case_scheduled.py::test_is_reminder_day` covers every day of one week; it fails on the old code and passes on the new.
- **Evening TypeError:** the close reminder subtracted `case.triage_at` from the current time, and `triage_at` was `None` for some triage cases. The job now uses `case.triage_at or case.created_at`. `test_case_close_reminder_without_triage_at_counts_from_created_at` fails without the fix and passes with it.
- **Likely source of the missing `triage_at`:** the Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets the status to triage without running the transition flow that records `triage_at`. I haven't confirmed this against case data, because the logs don't include case IDs. This bypass is still in the code.
- **Not changed:** the stable reminder still silently skips cases with no `stable_at`, and the reopen bypass is unchanged. Nothing is committed.
- **Reminders not resent:** reminders for 2025-08-18 and later Mondays were not sent and won't be sent automatically. Resending them is a separate decision.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```