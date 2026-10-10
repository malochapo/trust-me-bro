With no filters, the default dedup rule groups new instances into a recent case if they arrive within **45 minutes**. This is set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, which `filter_dedup` in `src/dispatch/signal/service.py` reads. An operator can change it by setting that environment variable, for example `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES=60`. The value is an integer number of minutes.

The `filter_signal` docstring in `service.py` still says "1-hour window". That text is out of date, because the code uses the 45-minute default.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py