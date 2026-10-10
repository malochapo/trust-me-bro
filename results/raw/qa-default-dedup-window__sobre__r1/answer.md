The window is 45 minutes. A signal definition with no filters groups a new instance into the case of the most recent instance of the same signal created within that window. That instance must already be attached to a case and must not be a canary.

The docstring of `filter_signal` in `src/dispatch/signal/service.py` still says "1-hour window". That text is out of date. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.

An operator changes the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, or the equivalent entry in Dispatch's config file, to an integer number of minutes. The setting is read once at startup, so the service needs a restart to pick up a new value.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py