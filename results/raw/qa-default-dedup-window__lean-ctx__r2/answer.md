When a signal definition has no filters, a new instance is deduplicated into the most recent case from the same signal if that case's instance was created within the last 45 minutes. The lookup is in `filter_dedup` (`src/dispatch/signal/service.py:804-823`). It looks for another non-canary instance of the same signal with a `case_id` and a `created_at` inside the window. If it finds one, it copies that `case_id` and marks the new instance as `deduplicate`. Canary instances are skipped.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a number of minutes. The default is 45 and the value is cast to an int (`config.py:95`).

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py