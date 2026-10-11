**Root cause:** `_is_reminder_day()` compares ISO weekday to the wrong constant. It's in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 because Python's `calendar` module counts Monday as 0. On this machine `calendar.MONDAY` evaluates to 0. The check is therefore false every day of the week. `case_close_reminder` (line 49) and `case_stable_reminder` (line 95) both call it, so neither ever sends. The daily triage reminder (`case_triage_reminder`) doesn't use the weekday check, so it keeps working. The incident reminders still use the old inline `date.today().isoweekday() == 1` at `src/dispatch/incident/scheduled.py:229`, which is correct, and that explains why incident close reminders still arrive.

**Introducing commit:** `c509d45e` "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12 14:05 -0700). It replaced the original `date.today().isoweekday() == 1` with `_is_reminder_day()`, which is where the bug was introduced. The original inline check was correct.

**Deploy:** The scheduler pod changed from `scheduler-xdp7k6gs2q-w6cj7` to `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40:11Z, and the API web pods also rolled at about the same time (api.log line 13205). That restart is the first one after `c509d45e` landed on main, and the next Monday (2025-08-18) is the first one where the reminders should have gone out and didn't. The logs contain no version or commit markers, so the link from the 08-13 restart to `c509d45e` is inferred from timing, not confirmed against a deploy record. A deploy record (CI or release log) would settle which release carried it.

**Evidence from the logs:**
- Monday 2025-08-04 and 2025-08-11 sent case close reminders (6 and 5 sends). These ran on the old code, before the 08-13 restart.
- No "Case close reminder sent" line appears anywhere after 2025-08-11. Monday 2025-08-18 has only incident close reminders.
- "Case triage reminder sent" continues daily through 2025-08-20 (33 sends total).

**Fix (not applied):** Compare against `Monday` as the ISO weekday, e.g. `date.today().isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`, since `weekday()` is the 0-based form that matches `calendar.MONDAY`. Adding a test that pins the reminder to a Monday date would prevent a repeat.

**Unrelated issue I noticed:** `case_close_reminder` still reads `case.triage_at` without a None guard (line 47). The per-case `try/except` contains it, but it logs a `TypeError` traceback for every triage case with no `triage_at` on every run (for example the 08-13 entries in scheduler.log). The stable reminder got that guard in `32fa810f`; the triage one did not.

No code has been changed.

----- next turn -----

The weekly close reminders are fixed, and I added a regression test that fails on the old code and passes on the fix. I haven't committed anything.

**The fix** is one line in `src/dispatch/case/scheduled.py:33`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0. I changed it to `date.today().weekday() == calendar.MONDAY`, which compares like with like.

**The regression test** is in a new file, `tests/case/test_case_scheduled.py`. It covers:
- `_is_reminder_day()` returns true on a pinned Monday and false on other days.
- `case_stable_reminder` and `case_close_reminder` each send for a case that has been in that status for 8 days, on a pinned Monday.
- `case_stable_reminder` sends nothing on a non-Monday.

It calls the undecorated task functions from the scheduler registry and stubs out `send_case_close_reminder`, so no real messages go out. Before the fix, the three Monday tests failed; after it, all 7 tests pass.

**Full suite:** 366 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those 8 on the untouched baseline, and they fail there too, so they predate this change and I didn't investigate them. `tests/case` passes in full (22 tests).

**Not changed:** `case_close_reminder` still reads `case.triage_at` without a None check, so every triage case missing that timestamp logs a `TypeError` each run. The per-case `try/except` keeps the other cases going. The stable reminder got the same guard in `32fa810f`, so adding it to the triage path is a small follow-up if you want it.

----- next turn -----

The close reminder no longer raises the `TypeError`. Cases with no `triage_at` now count from `created_at`, and they get their weekly reminder once they're at least a week old. The case tests pass (24).

**What causes it:** `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`), which runs only through the transition dispatcher on certain status changes. Any path that puts a case into Triage without running that branch leaves `triage_at` NULL, and the job then subtracts `None` from a datetime. Three paths can do this:
- **Slack reopen button** (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`, `reopen_button_click`): sets `case.status = CaseStatus.triage` and never calls the dispatcher. This is the clearest unflowed path.
- **Dispatcher catch-all** (`src/dispatch/case/flows.py:766`): an unexpected previous status logs a warning and does nothing else.
- **Case create** (`src/dispatch/case/service.py:205`): writes `status=case_in.status` directly, so a case created in Triage never gets the timestamp.

I can't tell from the logs which path produced the cases behind the nightly errors. The traceback doesn't include a case ID. The logs have zero "Unexpected previous state" warnings, which makes the catch-all path less likely, but I haven't ruled out the other two.

**The fix** is in `src/dispatch/case/scheduled.py:46-49`: `triage_start = case.triage_at or case.created_at`, and the span is measured from that.

**Tests** added to `tests/case/test_case_scheduled.py`:
- A triage case with no `triage_at` and a `created_at` 8 days old gets the reminder on a Monday. This test failed with the `TypeError` before the fix.
- A recent case with no `triage_at` (created 2 days ago) gets no reminder.

**Not changed:** the root cause. Setting `triage_at` in `reopen_button_click` (and the create path) would stop new cases from landing in this state. That's a behavior change to the Slack and create flows, so I left it for you to decide. I can make that change next if you want it.

----- next turn -----

Here is the recap for the incident report.

**Summary**

- **Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. Daily triage reminders kept arriving, and no settings changed.
- **Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0). The comparison was never true, so both the triage and stable close reminders were silently skipped every day.
- **Introduced:** commit `c509d45e` ("refactor(case): share the weekly reminder check"), which replaced the original, correct inline check with the helper.
- **Deployed:** the scheduler and web pods restarted on 2025-08-13 at about 16:40 UTC, running image `registry.example.com/dispatch:main-81d8ae42`. That image contains `c509d45e`. The previous image, `main-b05613b5`, does not. The logs show the Monday 2025-08-11 reminders were still sent under the previous image.
- **Impact:** the first missed Monday was 2025-08-18. The close reminders were not sent on that day or on any day afterward. Incident close reminders were not affected because they use their own inline check.
- **Fix:** `date.today().weekday() == calendar.MONDAY` in `src/dispatch/case/scheduled.py`. Regression tests in `tests/case/test_case_scheduled.py` failed on the old code and pass on the fix.

**Second issue:** the nightly `TypeError` comes from `case_close_reminder` subtracting `case.triage_at`, which is NULL for cases that reached Triage without running the triage transition flow. Known paths include the Slack reopen button, which sets the status directly, and case creation with a Triage status. The job now counts from `created_at` when `triage_at` is missing, and tests cover that. I have not changed those paths to set `triage_at`, and I could not tell from the logs which path produced the affected cases.

**Six-line summary for the report:**

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at