The function is `_should_update_signal_message`, and the minimum gap is 5 seconds.

It is called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:94`) only when a repeat is deduplicated into an existing case that has a conversation. It returns True only when the instance's filter action is `deduplicate`, the case has a `signal_thread_ts`, and at least `timedelta(seconds=5)` has passed since the cached last redraw for that case. When it returns True, `update_signal_message` redraws the post. The cache is a per-case `TTLCache` with `maxsize=4` and `ttl=60` seconds, so a case's last-redraw record expires after 60 seconds, and the first repeat after that expiry is always allowed through.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds