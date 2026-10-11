New signal instances on a signal with no filters are grouped into the most recent matching case within **45 minutes**. The docstring on `filter_signal` says 1 hour, but the code default is 45 minutes, so the code is the reference here.

The logic is in `filter_dedup` (`src/dispatch/signal/service.py:804-822`). It looks for the newest other instance of the same signal created in the window that has a `case_id`, ignoring canaries, and copies that case onto the new instance with the `deduplicate` filter action. Canary instances skip deduplication entirely.

To change it, set the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which is read as an integer. The default is 45 when it is unset. I did not run the code or check the config loader's precedence, so I haven't confirmed a value set in a `.env` file takes effect.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py