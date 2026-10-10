Recap: the weekly close and stable reminders are gated by _is_reminder_day, which compared isoweekday() (Monday = 1) with calendar.MONDAY (0), so it was never true. The commit that introduced it reached production with the scheduler rollout of 2025-08-13; Monday 2025-08-11 was the last one with reminders. The evening TypeError came from a case in triage that never got a triage timestamp; such cases now count from their creation.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: {plant:q4-reminder-day}
DEPLOYED_IMAGE: registry.example.com/dispatch:main-{plant:17b016b61a604caa0f0a090ec5ec018ca0c13dbf:short}
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
