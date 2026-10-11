New signal instances with no filters are grouped into the most recent matching case within a **45-minute** window. The default comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, and `filter_dedup` in `src/dispatch/signal/service.py` (around line 805) applies it. It looks for the newest instance of the same signal created in that window that already has a case, and attaches the new instance to that case.

An operator changes the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a whole number of minutes. The value is read at startup, so the app needs a restart after the change.

The docstring of `filter_signal` and the comment on `SignalFilter.window` in `src/dispatch/signal/models.py:208` both say one hour. The code default is 45 minutes, so those comments are stale.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py