When a signal has no filters, `filter_dedup` in `signal/service.py` (line 804 onward) looks back over a default window. It takes the most recent non-canary instance of the same signal that already has a case and was created inside that window. If it finds one, the new instance gets that instance's case and its filter action is set to `deduplicate`.

The default window is 45 minutes. An operator can change it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. The setting is read through `config(...)` in `config.py`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py