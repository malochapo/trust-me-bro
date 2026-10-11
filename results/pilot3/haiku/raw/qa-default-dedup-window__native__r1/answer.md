With no filters on the signal, new instances are grouped into an existing case if a matching instance was created within the last **45 minutes**. The check is in `filter_dedup` in `src/dispatch/signal/service.py` (around line 804). It only matches prior, non-canary instances that already have a case, and it attaches the new instance to the most recent one's case.

The `filter_signal` docstring says "1-hour window", but that text is stale. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which is read as an integer in minutes. I did not run anything to confirm the behavior.

This is separate from `SignalFilter.window`, which applies only to signals that have filters and is stored in seconds (default 3600).

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py