When a signal has no filters, a new instance is attached to the most recent non-canary instance of the same signal that already has a case. That instance must have been created within the default dedup window, which is 45 minutes. The logic is in `signal/service.py:804-822`. It sets `case_id` to the existing case and marks the instance as `deduplicate`.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. `config.py` reads it at startup, so the app needs a restart to pick up a new value.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py