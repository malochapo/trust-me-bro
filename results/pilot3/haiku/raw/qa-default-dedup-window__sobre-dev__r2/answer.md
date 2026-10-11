With no filters on a signal, new instances are grouped into a recent case if a matching instance landed in the last **45 minutes**. The default is set in `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which an operator can change through the environment variable of the same name.

The check is in `filter_dedup` (`src/dispatch/signal/service.py:805`). When `signal.filters` is empty, it looks for an earlier instance of the same signal with a case attached, created within the window, and reuses that instance's case. Canary instances are skipped.

Two things to be aware of:
- The `filter_signal` docstring (`service.py:873`) and the `SignalFilter.window` comment (`signal/models.py:208`) still say 1 hour. That is stale. The 1-hour figure only applies to explicit `SignalFilter` rules with `deduplicate` action, which default to `60 * 60` seconds, and those are configured per filter, not through the environment variable.
- I did not run anything. The conclusion comes from reading the code.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py