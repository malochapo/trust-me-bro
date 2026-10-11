The default window is 45 minutes. When a signal has no filters, a new instance is attached to the case of the most recent non-canary instance of the same signal created within that window. That earlier instance must already have a case. The new instance is marked with the `deduplicate` filter action. This logic is in `signal/service.py`.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes.

A docstring in `signal/service.py` (around line 873) still says "1-hour window". The code uses the 45-minute default, so the docstring is out of date.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py