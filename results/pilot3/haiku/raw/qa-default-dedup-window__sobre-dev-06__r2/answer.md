With no filters on the signal, new instances are grouped into an existing case if a matching instance was created within the last **45 minutes**. The window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read from the environment with a default of 45 (`src/dispatch/config.py:95-96`). The check runs in `filter_dedup` (`src/dispatch/signal/service.py`), which looks back from now and attaches the instance to the case of the most recent prior instance of the same signal that already has a case. Canary instances are excluded.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable on the Dispatch deployment and restarting the process. The value is an integer number of minutes.

The docstring of `filter_signal` in `src/dispatch/signal/service.py` says "1-hour window," which contradicts the 45-minute default in the code. The code is what runs, so I've treated 45 minutes as the answer. The docstring is stale.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py