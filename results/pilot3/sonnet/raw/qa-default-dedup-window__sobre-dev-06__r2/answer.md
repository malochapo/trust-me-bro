The window is 45 minutes by default. The docstring of `filter_signal` in `signal/service.py` still says "1-hour window", but that text is out of date. The code uses the setting below.

In `filter_dedup` in `src/dispatch/signal/service.py`, a signal with no filters is grouped into the most recent case of an earlier non-canary instance of the same signal. The instance must be newer than `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` minutes. An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. `config.py` reads it with `config(..., cast=int, default=45)`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py