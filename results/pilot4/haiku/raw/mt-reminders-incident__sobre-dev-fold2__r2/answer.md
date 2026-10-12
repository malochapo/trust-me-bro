**Recap**

- **Symptom:** assignees stopped getting the Monday reminders for long-running triage and stable cases from mid-August. Daily triage reminders kept going, and no reminder settings changed.
- **Root cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday test into `_is_reminder_day()`. That function compared `date.today().isoweekday()` against `calendar.MONDAY`, which is `0`, while `isoweekday()` returns `1` for Monday. The check was never true, so neither the close nor the stable reminders went out on Mondays.
- **Deploy:** the API log shows `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13 at 16:40Z. That build contains `c509d45e`. The scheduler's image isn't in the logs, so I'm inferring it was deployed with the API.
- **Evidence:** Monday 2025-08-11, before the deploy, still sent 5 case close reminders. Monday 2025-08-18, the first Monday after the deploy, sent none.
- **Fix:** `_is_reminder_day()` now compares against `1`. A regression test checks every weekday, and it fails on the old code.
- **Second issue:** the evening TypeError is in `case_close_reminder`. Cases moved to triage from the Slack handlers never get `triage_at` set, so the job's subtraction fails for them. The job now falls back to `created_at`, with a test. The Slack handlers themselves still skip the triage flow and were not changed.
- **Side effect of the same deploy:** `32fa810f` guarded the stable reminder against a missing `stable_at`. That stopped its daily error, but cases without `stable_at` still get no stable reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at