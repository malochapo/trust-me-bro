A signal with no filters groups new instances into the most recent case for **45 minutes** by default. The lookback is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/signal/service.py` (`filter_dedup`, around line 805), which reads it from the environment.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a different number of minutes. The value is parsed as an integer in `src/dispatch/config.py`.

The docstring on `filter_signal` (around line 873) says "1-hour window", which contradicts the 45-minute default in code. The code is the source of truth here, so the docstring looks stale.

The window only matches instances that already belong to a case, and it ignores canary instances.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py