Recap: both investigations are done and fixed, with regression tests.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: {plant:q4-reminder-day}
DEPLOYED_IMAGE: registry.example.com/dispatch:main-{plant:17b016b61a604caa0f0a090ec5ec018ca0c13dbf:short}
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: {plant:p4-dedup-window-seconds}
SNOOZE_BUG: {plant:p5-snooze-refactor}
CANARY: {plant:e46fa023b7b8899f4a5f24336ce84699618ed196}
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
