When a signal has no filters, `filter_dedup` in `signal/service.py` looks for another instance of the same signal that was created within the default dedup window and already belongs to a case. If it finds one, the new instance is attached to that case and marked as deduplicated.

The window is **45 minutes**. The docstring of `filter_signal` still says "1-hour window", but the code uses 45 minutes, so the docstring is out of date.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a whole number of minutes. `config.py` reads it with `config(..., cast=int, default=45)`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py