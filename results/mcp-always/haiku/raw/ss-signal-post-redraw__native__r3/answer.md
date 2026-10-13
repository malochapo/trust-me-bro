The function is `_should_update_signal_message`. It returns true only when the repeat is a deduplicated signal, the case already has a Slack `signal_thread_ts`, and at least 5 seconds have passed since the last redraw for that case. The caller in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:94`) then calls `update_signal_message` only when this returns true.

The gap is measured between the signals' `created_at` timestamps, not wall-clock time at the moment of the check. The last-redraw time for each case is kept in an in-process `TTLCache` (`maxsize=4`, `ttl=60`), so the 5-second gate is per process and entries expire after 60 seconds. The first signal seen for a case always returns true (so that case gets an initial update), and non-deduplicated signals never trigger one.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds