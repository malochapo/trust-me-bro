With no filters on the signal, new instances are grouped into an existing case if a sibling instance with a case was created within the last **45 minutes**. The lookup is in `filter_dedup` (`src/dispatch/signal/service.py:804-823`). It matches on `signal_id`, skips canaries and the instance itself, and attaches to the case of the most recent match.

The window is set by the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, read in `src/dispatch/config.py:95-97` with a default of 45. An operator changes it by setting that variable in the deployment environment and restarting the service. The value is an integer number of minutes.

The docstring for `filter_signal` (`service.py:872-874`) says the default is a 1-hour window. That is stale; the code uses 45 minutes unless the variable overrides it.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py