With no filters on the signal, a new instance is grouped into the most recent matching case if that case's instance is within **45 minutes**. The match is on the same signal, regardless of entities. Only instances that already belong to a case count, canary instances are ignored, and the newest match wins.

An operator changes this with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. The default of 45 is defined in `config.py` and read through `config()`, so it can also be set in the environment or `.env`. The window is read on each dedup check, so it applies to new instances without any code change. The `filter_signal` docstring says "1-hour window," which contradicts the 45-minute default in code. The code is the source of truth here.

The dedup logic is in `filter_dedup` in `src/dispatch/signal/service.py`, around lines 800–830.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py