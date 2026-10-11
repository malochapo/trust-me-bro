The default window is 45 minutes. When a signal has no filters, `filter_dedup` in `src/dispatch/signal/service.py` looks for another instance of the same signal created within that window that already belongs to a case. If it finds one, the new instance is attached to that case.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. It is read in `config.py` as an integer number of minutes, with a default of 45.

The docstring on the calling function in `service.py` says "1-hour window", but that text is out of date. The code uses the setting, which defaults to 45 minutes.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py