A signal with no filters groups new instances into the most recent case for that signal if the case was created within the last **45 minutes**. The window is set by the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which defaults to 45. An operator changes it by setting that variable in the deployment environment and restarting the service. There is no per-signal or UI setting for it.

The logic is in `filter_dedup` in `src/dispatch/signal/service.py`. It looks for the latest other instance of the same signal, created inside the window, that already has a `case_id`, and copies that case onto the new instance with the `deduplicate` filter action. Canary instances are ignored on both sides.

The docstring on the calling function (`src/dispatch/signal/service.py`, around line 873) says the default groups instances "for a 1-hour window". That doesn't match the code's 45-minute default, so the docstring is stale.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py