**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It was shipped by the production deploy that rolled out on 2025-08-13 at about 16:40Z. I haven't changed any code.

**The bug**

The commit replaced `date.today().isoweekday() == 1` with a shared helper in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I confirmed this by running it). The condition is now never true. `case_close_reminder` and `case_stable_reminder` both call the helper, so neither sends again. The daily triage reminder doesn't use the helper, which is why it kept working. Nothing in the settings changed. The commit was labelled a refactor and looked behaviour-neutral, so the change in meaning went unnoticed.

**Evidence from the logs**

- **Before the deploy:** Monday 18:00Z runs sent case close reminders on 07-28 (4 case reminders), 08-04 and 08-11 (about 6 each). On 08-11 `case_close_reminder` and `case_stable_reminder` took about 1.3 s.
- **After the deploy:** the Monday 08-18 run sent no case close reminders, and neither did the stable reminder. Both functions finished in about 0.03–0.05 s. The only "close reminder" line that day is an incident one, and the triage reminder was still sent.
- **Deploy time:** the scheduler pod changed from `scheduler-xdp7k6gs2q-w6cj7` to `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40Z. The API pod changed at the same moment, from `web-bsnvb5wc2t-7lt2t` to `web-5dkmr9s9s-xxktx`. The new pod's traceback line numbers in `case_close_reminder` moved from 43 to 47, which is consistent with the new helper code being present. That deploy is the first one after the 08-12 commit.
- **Not the cause:** the Aug 14 commit `917a0b7b` (signal lookback window) is unrelated, and nothing in `src` sets a timezone.

**What I couldn't confirm**

I don't have the deploy pipeline or image tags, only the pod rollover times. I'm inferring that this deploy contains `c509d45e` from the timing and the line-number shift. The commit landed 2025-08-12 at 14:05 -0700, which is 21:05Z, about 19.5 hours before the rollover. The deployed code's traceback line numbers (43/93 before, 47 after) don't match any version of the file in this repo's history (41/87), so I can't pin the exact deployed commit that way.

**A separate bug, not the cause here**

`case_close_reminder` doesn't handle a case with no `triage_at`. It logs `TypeError ... NoneType` on every run, both before and after the deploy. The same applies to `case_stable_reminder` on `stable_at` before commit `32fa810f`. That is noise and isn't what stopped the reminders.

**Fix, when you want it:** compare against `calendar.MONDAY` using `date.today().weekday()`, or restore `isoweekday() == 1`. The same pattern sits at `src/dispatch/incident/scheduled.py:229`, which still uses the correct `== 1`, so incident reminders are unaffected. A unit test that freezes a Monday would have caught this. Tell me if you want me to make the change.

----- next turn -----

Fixed and covered by a regression test, which fails on the old code and passes on the fix. I haven't committed anything.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use the same numbering, with Monday as 0. Before, `isoweekday()` (Monday is 1) was compared against `calendar.MONDAY` (0), so the check never passed.

**Test** (`tests/case/test_case_scheduled.py`, new):
- `test_is_reminder_day` freezes the date across a full week plus the following Monday. It expects true only on Mondays.
- `test_weekly_reminders_only_sent_on_mondays` runs the real `case_close_reminder` and `case_stable_reminder` task bodies with a case that is 10 days old. It expects a reminder on Monday and none on Tuesday.
- Together they cover both the helper and the tasks that call it.

**Verification:**
- With the fix, all 10 tests pass.
- With only the `src` change stashed, 3 of the 10 fail: the two Monday cases of `test_is_reminder_day` and the Monday case of the task test.
- I only ran `tests/case/test_case_scheduled.py`, not the full suite.

The other bug I flagged earlier is still there. `case_close_reminder` errors on a case with no `triage_at`. It is caught per case and logged, so it doesn't stop reminders. I left it alone because it's separate from this fix.

After you deploy, the first Monday 18:00Z run should log "Case close reminder sent" lines again. Assignees won't get the reminders until then, and nothing is sent retroactively for the Mondays that were missed.

----- next turn -----

The daily TypeError is fixed, and cases with no `triage_at` now get their weekly reminder, counted from `created_at`. I haven't committed anything.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at` for every case in triage status. Some of those cases have `triage_at` set to NULL, so the subtraction fails with `TypeError: ... 'datetime.datetime' and 'NoneType'`.

Two things in the code explain how that happens:
- The column was added in 2022 as nullable, in migration `391f7c3e6992`, and I saw no backfill for it.
- `triage_at` is only set by `case_triage_status_flow` in `src/dispatch/case/flows.py`. Case creation passes `status=case_in.status` straight through and doesn't set it.

I can't query the database, so I haven't confirmed which cases are affected. The logs show the error every evening, even before the deploy that broke the Monday check.

**Why it went unnoticed:** the error is caught per case and logged, so the other cases still went out. The affected cases never got a reminder.

**Fix** (`src/dispatch/case/scheduled.py`): the age is now counted from `case.triage_at or case.created_at`. `created_at` is already loaded by `get_all_by_status`.

**Tests** (added to `tests/case/test_case_scheduled.py`): four cases on a frozen Monday.
- No `triage_at` and 10 days old: a reminder is sent.
- No `triage_at` and 3 days old: no reminder.
- `triage_at` set and older than `created_at`: it takes precedence, so a reminder is sent.
- `triage_at` set and newer than `created_at`: it takes precedence, so no reminder.

Each case also asserts that nothing was logged as an exception. All 14 tests in the file pass. To check they fail without the fix, I stashed the `src` changes, which also reverted the Monday fix from earlier. That gave 6 failures, including all the new no-`triage_at` cases. I only ran this file, not the full suite.

I left `case_stable_reminder` alone. It skips cases with no `stable_at` rather than erroring, and you only asked about the close reminder. Say if you want it to fall back to `created_at` too.

----- next turn -----

In my earlier answer I said I couldn't confirm which build contained the bad commit. I had missed the kubelet "Started container" lines in both logs, which give the image tags. Here is the corrected recap.

**Weekly Monday reminders (the main outage)**
- **What happened:** commit `c509d45e`, a refactor, moved the Monday check into `_is_reminder_day()`. It compares `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so it is never true.
- **Effect:** `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) stopped sending. `case_triage_reminder` doesn't use the helper, so it kept working.
- **Deploy:** the image `registry.example.com/dispatch:main-81d8ae42` started on both the scheduler and the web pods at 2025-08-13 ~16:40Z. The previous image was `main-b05613b5`, running since 2025-07-30. `81d8ae42` is a descendant of `c509d45e` (12 Aug 14:47 vs 14:05 -0700), so it contains the bug. The old image does not.
- **Last good Monday:** 2025-08-11, with about 6 reminders sent. On 2025-08-18, none were sent, and the jobs ran in about 0.03–0.05 s instead of about 1.3 s.
- **Fix:** `_is_reminder_day()` now uses `weekday()`, with a regression test.

**Evening TypeError (separate issue)**
- **What happened:** `case_close_reminder` computed `utcnow() - case.triage_at`. Some cases in triage status have `triage_at` set to NULL. Likely reasons are that the column was added in 2022 without a backfill and that case creation doesn't set it. I haven't checked the database.
- **Effect:** each affected case logged the error and was skipped, so those cases never got a reminder. This predates the outage.
- **Fix:** the age is now counted from `triage_at or created_at`, with tests.

Neither fix is committed or deployed yet. Missed Mondays are not retroactively sent: 2025-08-18, 2025-08-25 and every Monday after that until the fix ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at