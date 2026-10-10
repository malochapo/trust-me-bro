The default grouping window is 45 minutes. In `filter_dedup` in `signal/service.py`, a signal with no filters is attached to the most recent non-canary instance of the same signal that already has a case and was created inside that window.

An operator can change it with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. It is an integer number of minutes and is read through the config helper in `config.py`.

The docstring of the dedup function (around line 873 of `signal/service.py`) still says "1-hour window". That is out of date, because the code uses the 45-minute setting.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py