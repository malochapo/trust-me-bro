The window is 45 minutes by default. An operator can change it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which is read through Dispatch's config layer and cast to an integer.

When a signal has no filters, `filter_dedup` in `src/dispatch/signal/service.py` looks for the most recent instance of the same signal. That instance must be newer than the window, already attached to a case, and not a canary. If it finds one, the new instance joins that case and is marked `deduplicate`.

The docstring of `filter_signal` still says "1-hour window". That text is out of date, because the code uses the setting and its default is 45 minutes.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py