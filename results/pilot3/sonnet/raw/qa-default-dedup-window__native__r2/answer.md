The window is 45 minutes by default. The `filter_signal` docstring in `signal/service.py` still says "1-hour window", but that is stale. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.

When a signal has no filters, `filter_dedup` in `signal/service.py` applies a default rule. It groups the new instance into a recent case if a matching instance was created within that window. An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. Dispatch reads it through `config(...)` in `config.py`, and it takes effect when the service restarts.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py