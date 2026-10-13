The function is `_should_update_signal_message`. It decides whether a deduplicated repeat triggers a redraw of the alert's post in the case thread, and it only returns true when at least 5 seconds have passed since the last redraw for that case.

It is called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py:94`. The redraw itself is `update_signal_message` (`flows.py:329`), which calls the Slack plugin's `update_signal_message`.

The rule, as written in `_should_update_signal_message`:
- The first signal seen for a case always updates (the case is not yet in the cache).
- A later signal updates only if its `filter_action` is `deduplicate`, the case has a `signal_thread_ts`, and `created_at` minus the cached last-update time is at least 5 seconds.
- Otherwise it returns false.

The cache is a `TTLCache(maxsize=4, ttl=60)`. The 60-second TTL is how long an entry is kept, not the redraw gap, so it doesn't change the 5-second minimum. The cache is in-process memory and holds at most 4 cases, so the gap check is per process.

I did not change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds