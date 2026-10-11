With no filters, the default window is 45 minutes. The docstring at `signal/service.py:873` says "1-hour window", but that text is out of date. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 (`config.py:95-96`). An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a whole number of minutes. Dispatch reads it through its config loader, so the server needs a restart for a new value to apply.

Instances are grouped only if they were created within that window, and canary signals are ignored.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py