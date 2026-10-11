When a signal definition has no filters, new instances are grouped into an existing case if another instance of the same signal, linked to a case, was created within the last **45 minutes**. The match ignores entities, and the new instance takes the case of the most recent such instance (`src/dispatch/signal/service.py`, `filter_dedup`). The docstring for `filter_signal` says 1 hour, which is stale: the code uses the 45-minute config default.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which is read as an integer number of minutes. It applies to all signals without filters. Signals that do have filters use each filter's own `window` field (in seconds) instead.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py