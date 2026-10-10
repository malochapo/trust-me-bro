When a signal definition has no filters, Dispatch applies a default dedup rule. It groups new instances into a recent case if they arrive within **45 minutes**. The code is in `filter_dedup` in `signal/service.py`, around line 805. It builds the window as `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)` and matches instances created at or after that time.

The `filter_signal` docstring still says "1-hour window". That text is out of date, because the code uses the 45-minute default.

An operator changes the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. The value is read through `config(...)` with `cast=int`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py