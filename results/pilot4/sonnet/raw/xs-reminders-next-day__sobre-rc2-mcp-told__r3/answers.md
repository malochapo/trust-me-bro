**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check. The new helper in `src/dispatch/case/scheduled.py:31-33` is:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1–7, with Monday as 1. `calendar.MONDAY` is 0, so the comparison is never true on any day. The old inline check was `isoweekday() == 1`. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) now call this helper. Neither sends its weekly reminder any more, and nothing logs an error. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, so it kept working.

The correct check is `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`. I haven't changed any code.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. The kubelet started it at 2025-08-13 16:40Z, on the scheduler pod `scheduler-mhtsgqwwx-q5q2n` and the web pod `web-5dkmr9s9s-xxktx`. `c509d45e` is an ancestor of `81d8ae42` and not of the previous image, `main-b05613b5`, which ran from 2025-07-30 17:10Z. I confirmed the ancestry with git.

**What the logs show:**
- On Monday 2025-08-11 (old image), the scheduler logged "Case close reminder sent" for five assignees at 18:00: `r.patel`, `s.lindqvist`, `a.chen`, `m.okafor` and `k.tanaka`.
- On Monday 2025-08-18 (new image), the 18:00 run logged no close reminders at all, and no new errors apart from the old one below. The triage reminders still went out.
- The earlier Monday, 2025-08-04, was in the same state as the 11th. I didn't read its sends.

**Unrelated noise, not the cause:**
- `TypeError … NoneType` errors, raised when a case has no `triage_at` or `stable_at`. They appear in the daily 18:00 runs before the deploy, and the `stable_at` guard was added in `32fa810f` on 2025-08-11.
- `case_close_reminder` still logs the `triage_at` error after the deploy, on cases with no `triage_at`. It's caught per case and doesn't stop the other cases.
- Slack rate-limit errors, "No … plugin enabled" warnings, and a database "starting up" error on 2025-08-15.

Once this is fixed, the next Monday run will send the reminders again. Nothing queues up for the Mondays that were missed (08-18 so far, and later ones until it ships).

----- next turn -----

Weekly case reminders are fixed. The new tests pass with the fix and fail without it (3 failures against the old code).

**Cause:** commit `c509d45e` ("share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`. It compared `date.isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. The check was therefore never true on any day, so `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) stopped sending.

**Evidence in the logs:** reminders went out on Monday 2025-07-28, 08-04 and 08-11. The 08-12 commit first reached production in the `main-81d8ae42` rollout on 2025-08-13 at 16:40 UTC. On 08-18 the triage and stable reminder jobs ran at 18:00 but sent nothing.

**Fix:** in `src/dispatch/case/scheduled.py` I replaced `calendar.MONDAY` with a `MONDAY = 1` constant and a comment explaining the numbering. I also removed the now-unused `calendar` import.

**Test:** `tests/case/test_case_scheduled.py` checks that `_is_reminder_day()` is true only on Monday. It also checks that both reminder jobs send on a Monday and not on a Tuesday for a case that is over a week old.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18