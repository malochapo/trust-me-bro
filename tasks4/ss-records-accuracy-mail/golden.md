create_evergreen_reminders is registered with @scheduler.add(every().monday.at("18:00")). It collects the overdue evergreen documents, services, teams and notifications and e-mails each owner through create_evergreen_reminder. An item is overdue when its evergreen_reminder_interval (EvergreenMixin default: 90 days) has passed since evergreen_last_reminder_at.

FILE: src/dispatch/evergreen/scheduled.py
FUNCTION: create_evergreen_reminders
RUNS: Monday 18:00
DEFAULT_DAYS: 90
